import asyncio
import json
import logging
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    BotCommand,
)
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID, WEBAPP_URL, ENABLE_WEBAPP_SERVER, WEBAPP_HOST, WEBAPP_PORT
import database as db
from dnevnik_client import DnevnikClient, DnevnikUnauthorizedError, DnevnikExternalServerError
from formatters import (
    esc_md,
    format_homework_message,
    format_schedule_message,
    format_period_grades_message,
    format_week_grades_message,
    format_year_grades_message,
    format_calls_message,
    format_help_message,
    WEEKDAYS,
)
from refresher import run_tokens_refresher_loop
from webapp_server import run_webapp_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dnevnik_bot")

dp = Dispatcher(storage=MemoryStorage())


# Helper: get client for user with token decryption and auto-save on refresh
async def get_client(telegram_id: int) -> DnevnikClient | None:
    user = await db.get_user(telegram_id)
    if not user or not user.get("access_token") or not user.get("refresh_token"):
        return None

    async def on_refreshed(new_access: str, new_refresh: str):
        meta = user.get("meta", {})
        await db.save_tokens(telegram_id, new_access, new_refresh, meta=meta)
        logger.info(f"Updated refreshed tokens in database for user {telegram_id}")

    return DnevnikClient(
        access_token=user["access_token"],
        refresh_token=user["refresh_token"],
        on_token_refreshed=on_refreshed,
    )


# Helper: generate user reply buttons with personalized class name
async def get_reply_keyboard(telegram_id: int) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    user = await db.get_user(telegram_id)
    if not user or not user.get("access_token"):
        return ReplyKeyboardRemove()

    class_name = user.get("meta", {}).get("className", "")
    if not class_name:
        try:
            client = await get_client(telegram_id)
            if client:
                p = await client.profile()
                class_name = p.get("className", "")
                if class_name:
                    meta = user.get("meta", {})
                    meta["className"] = class_name
                    await db.save_tokens(telegram_id, user["access_token"], user["refresh_token"], meta=meta)
        except Exception:
            class_name = ""

    b_sched = KeyboardButton(text=f"🗓 Расписание {class_name}".strip())
    b_tomorrow = KeyboardButton(text="На завтра")
    b_today = KeyboardButton(text="На сегодня")
    b_all_grades = KeyboardButton(text="📋 Все оценки")
    b_hw = KeyboardButton(text="✍️ Домашние задания")
    b_w_grades = KeyboardButton(text="📋 Оценки на этой неделе")
    b_help = KeyboardButton(text="📄 Список команд")

    return ReplyKeyboardMarkup(
        keyboard=[
            [b_sched],
            [b_tomorrow, b_today],
            [b_all_grades],
            [b_hw, b_w_grades],
            [b_help],
        ],
        resize_keyboard=True,
    )


def get_unreg_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Регистрация", callback_data="reg")]
        ]
    )


# -------------------------------------------------------------
# Commands & Handlers
# -------------------------------------------------------------

@dp.message(Command("db"))
async def show_users_admin(message: Message):
    if message.from_user.id == ADMIN_TELEGRAM_ID and ADMIN_TELEGRAM_ID != 0:
        user_ids = await db.get_all_user_ids()
        res = f"Зарегистрированные пользователи\\: *{len(user_ids)}*\n\n"
        for i, uid in enumerate(user_ids, 1):
            res += f"{i}\\. `{uid}`\n"
        await message.answer(res, parse_mode="MarkdownV2")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("access_token"):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 Список команд", callback_data="help")],
                [InlineKeyboardButton(text="✏️ Регистрация", callback_data="reg")],
            ]
        )
        await message.answer(
            "Здравствуйте! Зарегистрируйтесь, чтобы в дальнейшем пользоваться ботом",
            reply_markup=kb,
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 Список команд", callback_data="help")]
            ]
        )
        reply_kb = await get_reply_keyboard(message.from_user.id)
        await message.answer("Вы уже зарегистрированы", reply_markup=reply_kb)


@dp.message(Command("login"))
async def cmd_login(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("access_token"):
        webapp = WebAppInfo(url=WEBAPP_URL)
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Регистрация", web_app=webapp)]],
            resize_keyboard=True,
        )
        await message.answer(
            "Чтобы зарегистрироваться, нажмите кнопку снизу\\.\n"
            "Также прочтите инструкцию внутри формы\\.",
            reply_markup=kb,
            parse_mode="MarkdownV2",
        )
    else:
        reply_kb = await get_reply_keyboard(message.from_user.id)
        await message.answer("Вы уже зарегистрированы", reply_markup=reply_kb)


@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    user_id = message.from_user.id
    try:
        temp = json.loads(message.web_app_data.data)
        access_token = temp.get("accessToken", "").strip()
        refresh_token = temp.get("refreshToken", "").strip()

        client = DnevnikClient(access_token=access_token, refresh_token=refresh_token)
        new_access, new_refresh = await client.refresh_tokens()

        # Fetch profile to store student details
        profile = await client.profile()
        meta = {
            "firstName": profile.get("firstName", ""),
            "lastName": profile.get("lastName", ""),
            "surName": profile.get("surName", ""),
            "className": profile.get("className", ""),
            "orgName": profile.get("orgName", ""),
        }

        await db.save_tokens(user_id, new_access, new_refresh, meta=meta, selected_student_id=profile.get("id"))

        reply_kb = await get_reply_keyboard(user_id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📄 Список команд", callback_data="help")]]
        )
        await message.answer("Вы успешно зарегистрировались!", reply_markup=reply_kb)
        await message.answer("Выберите действие в меню снизу или откройте список команд:", reply_markup=kb)

    except (DnevnikUnauthorizedError, Exception) as e:
        logger.error(f"Login error: {e}")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✏️ Попробовать снова", callback_data="reg")]]
        )
        await message.answer(
            "Произошла ошибка. Возможно, вы ввели неверные или устаревшие токены.\nПопробуйте заново 👇",
            reply_markup=kb,
        )


@dp.message(Command("help"))
@dp.message(F.text.contains("Список команд"))
async def cmd_help(message: Message):
    reply_kb = await get_reply_keyboard(message.from_user.id)
    await message.answer(format_help_message(), reply_markup=reply_kb, parse_mode="MarkdownV2")


@dp.message(Command("calls"))
async def cmd_calls(message: Message):
    await message.answer(format_calls_message(), parse_mode="MarkdownV2")


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        p = await client.profile()
        res = (
            f"{p.get('lastName', '')} {p.get('firstName', '')} {p.get('surName', '')} {p.get('className', '')}\n"
            f"{p.get('orgName', '')}\n\n"
            "Удалить аккаунт — /delacc"
        )
        await message.answer(res)
    except Exception as e:
        logger.error(f"Profile error: {e}")
        await message.answer("Не удалось получить данные профиля.")


@dp.message(Command("delacc"))
async def cmd_delacc(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("access_token"):
        await message.answer("Чтобы удалить аккаунт, нужно сначала зарегистрироваться", reply_markup=get_unreg_keyboard())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data="deleteacc1"),
                InlineKeyboardButton(text="Нет, отмена", callback_data="deleteacc0"),
            ]
        ]
    )
    await message.answer("Удалить аккаунт?", reply_markup=kb)


# -------------------------------------------------------------
# Schedule Handlers
# -------------------------------------------------------------

async def send_schedule_day(message_or_query: Message | CallbackQuery, day_idx: int):
    user_id = message_or_query.from_user.id
    client = await get_client(user_id)
    target = message_or_query.message if isinstance(message_or_query, CallbackQuery) else message_or_query

    if not client:
        await target.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        lessons = await client.schedule(day_idx)
        text = format_schedule_message(day_idx, lessons)
        await target.answer(text, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Schedule error: {e}")
        await target.answer("Не удалось загрузить расписание.")


@dp.message(Command("today"))
@dp.message(F.text == "На сегодня")
async def cmd_today(message: Message):
    day_idx = datetime.now().weekday()
    await send_schedule_day(message, day_idx)


@dp.message(Command("nextday"))
@dp.message(F.text == "На завтра")
async def cmd_nextday(message: Message):
    day_idx = (datetime.now().weekday() + 1) % 7
    await send_schedule_day(message, day_idx)


@dp.message(Command("all"))
@dp.message(F.text.startswith("🗓 Расписание"))
async def cmd_schedule_all(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Понедельник", callback_data="schedule0"), InlineKeyboardButton(text="Вторник", callback_data="schedule1")],
            [InlineKeyboardButton(text="Среда", callback_data="schedule2"), InlineKeyboardButton(text="Четверг", callback_data="schedule3")],
            [InlineKeyboardButton(text="Пятница", callback_data="schedule4"), InlineKeyboardButton(text="Суббота", callback_data="schedule5")],
        ]
    )
    await message.answer("Выберите день", reply_markup=kb)


# -------------------------------------------------------------
# Grades Handlers
# -------------------------------------------------------------

@dp.message(Command("grades"))
@dp.message(F.text == "📋 Все оценки")
async def cmd_grades(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Текущая неделя", callback_data="wgrades")],
            [InlineKeyboardButton(text="1 четверть", callback_data="pgrades0"), InlineKeyboardButton(text="2 четверть", callback_data="pgrades1")],
            [InlineKeyboardButton(text="3 четверть", callback_data="pgrades2"), InlineKeyboardButton(text="4 четверть", callback_data="pgrades3")],
            [InlineKeyboardButton(text="По четвертям", callback_data="ygrades")],
        ]
    )
    await message.answer("Выберите период", reply_markup=kb)


@dp.message(Command("wgrades"))
@dp.message(F.text.contains("на этой неделе"))
async def cmd_wgrades(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        gr = await client.grades_week()
        text = format_week_grades_message(gr)
        await message.answer(text, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Week grades error: {e}")
        await message.answer("Не удалось получить оценки за неделю.")


@dp.message(Command("pgrades"))
async def cmd_pgrades(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        year_grades = await client.grades_year()
        text = format_year_grades_message(year_grades)
        reply_kb = await get_reply_keyboard(message.from_user.id)
        await message.answer(text, reply_markup=reply_kb, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Year grades error: {e}")
        await message.answer("Не удалось получить четвертные оценки.")


async def send_period_grades(message_or_query: Message | CallbackQuery, period_idx: int):
    user_id = message_or_query.from_user.id
    client = await get_client(user_id)
    target = message_or_query.message if isinstance(message_or_query, CallbackQuery) else message_or_query

    if not client:
        await target.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        disciplines = await client.grades_period(period_idx)
        text = format_period_grades_message(period_idx + 1, disciplines)
        reply_kb = await get_reply_keyboard(user_id)
        await target.answer(text, reply_markup=reply_kb, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Period grades error: {e}")
        await target.answer("Не удалось получить оценки за четверть.")


# -------------------------------------------------------------
# Homework Handlers (with day-by-day interactive pagination)
# -------------------------------------------------------------

def build_hw_keyboard(pagination: dict) -> InlineKeyboardMarkup:
    prev_date = pagination.get("previousDate")
    next_date = pagination.get("nextDate")

    has_prev = bool(prev_date and prev_date != "0001-01-01")
    has_next = bool(next_date and next_date != "0001-01-01")

    row = []
    if has_prev:
        row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"hw{prev_date}"))
    else:
        row.append(InlineKeyboardButton(text="🚫", callback_data="hwnoop"))

    row.append(InlineKeyboardButton(text="📅 Сегодня", callback_data="hwtoday"))

    if has_next:
        row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"hw{next_date}"))
    else:
        row.append(InlineKeyboardButton(text="🚫", callback_data="hwnoop"))

    return InlineKeyboardMarkup(inline_keyboard=[row])


@dp.message(Command("homework"))
@dp.message(F.text.contains("Домашние"))
async def cmd_homework(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        hw_data = await client.homework(None)
        text = format_homework_message(hw_data)
        kb = build_hw_keyboard(hw_data.get("pages", {}))
        await message.answer(text, reply_markup=kb, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Homework error: {e}")
        await message.answer("Не удалось загрузить домашнее задание.")


# -------------------------------------------------------------
# Callback Query Handlers
# -------------------------------------------------------------

@dp.callback_query()
async def handle_callback_query(query: CallbackQuery):
    data = query.data or ""
    user_id = query.from_user.id
    client = await get_client(user_id)

    if data == "reg":
        await cmd_login(query.message)
        await query.answer()
        return

    if data == "help":
        await cmd_help(query.message)
        await query.answer()
        return

    if not client:
        await query.message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        await query.answer()
        return

    if data.startswith("schedule"):
        day_idx = int(data[-1])
        try:
            await query.message.delete()
        except Exception:
            pass
        await send_schedule_day(query, day_idx)

    elif data.startswith("deleteacc"):
        if data[-1] == "1":
            await db.delete_tokens(user_id)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="✏️ Повторная регистрация", callback_data="reg")]]
            )
            await query.message.answer("Ваш аккаунт удален", reply_markup=kb)
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            try:
                await query.message.delete()
            except Exception:
                pass

    elif data.startswith("pgrades"):
        period_idx = int(data[-1])
        try:
            await query.message.delete()
        except Exception:
            pass
        await send_period_grades(query, period_idx)

    elif data == "wgrades":
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            gr = await client.grades_week()
            text = format_week_grades_message(gr)
            await query.message.answer(text, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Week grades error: {e}")
            await query.message.answer("Не удалось получить оценки за неделю.")

    elif data == "ygrades":
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            year_grades = await client.grades_year()
            text = format_year_grades_message(year_grades)
            reply_kb = await get_reply_keyboard(user_id)
            await query.message.answer(text, reply_markup=reply_kb, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Year grades error: {e}")
            await query.message.answer("Не удалось получить четвертные оценки.")

    elif data.startswith("hw"):
        code = data[2:]
        if code == "noop":
            await query.answer("Дальше заданий нет", show_alert=False)
            return

        date_str = None if code == "today" else code
        try:
            hw_data = await client.homework(date_str)
            text = format_homework_message(hw_data)
            kb = build_hw_keyboard(hw_data.get("pages", {}))
            try:
                await query.message.edit_text(text, reply_markup=kb, parse_mode="MarkdownV2")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"HW navigation error: {e}")
            await query.answer("Не удалось загрузить ДЗ на эту дату")
            return

    await query.answer()


# -------------------------------------------------------------
# Main Application Launcher
# -------------------------------------------------------------

async def set_my_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🏠 Запустить бота"),
        BotCommand(command="today", description="📅 Расписание на сегодня"),
        BotCommand(command="nextday", description="📅 Расписание на завтра"),
        BotCommand(command="all", description="🗓 Расписание на любой день"),
        BotCommand(command="grades", description="📋 Все оценки"),
        BotCommand(command="wgrades", description="📋 Оценки на этой неделе"),
        BotCommand(command="pgrades", description="📋 Четвертные оценки"),
        BotCommand(command="homework", description="✍️ Домашнее задание"),
        BotCommand(command="profile", description="👤 Профиль ученика"),
        BotCommand(command="calls", description="🔔 Расписание звонков"),
        BotCommand(command="help", description="📄 Список команд"),
        BotCommand(command="login", description="✏️ Регистрация"),
        BotCommand(command="delacc", description="❌ Удалить аккаунт"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Could not set commands: {e}")


async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment or .env file!")
        sys.exit(1)

    await db.init_db()

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await set_my_commands(bot)

    refresher_task = asyncio.create_task(run_tokens_refresher_loop())

    if ENABLE_WEBAPP_SERVER:
        asyncio.create_task(run_webapp_server(host=WEBAPP_HOST, port=WEBAPP_PORT))

    logger.info("Bot started and polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        refresher_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
