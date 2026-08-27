import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
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

from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_TELEGRAM_ID,
    WEBAPP_URL,
    ENABLE_WEBAPP_SERVER,
    WEBAPP_HOST,
    WEBAPP_PORT,
    SCHOOL_YEAR,
)
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
import rich_formatters as rf
from refresher import run_tokens_refresher_loop
from webapp_server import run_webapp_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dnevnik_bot")

dp = Dispatcher(storage=MemoryStorage())


# -------------------------------------------------------------
# Telegram Rich Messages (Bot API 10.1+) Dispatcher Helpers
# -------------------------------------------------------------

async def send_rich_msg(
    bot: Bot,
    chat_id: int,
    blocks: list,
    fallback_text: str,
    reply_markup: any = None,
) -> any:
    """
    Sends native Telegram Rich Message blocks (Table, Headings, Dividers, Details),
    automatically falling back to MarkdownV2 message if unsupported.
    """
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload: dict = {
        "chat_id": chat_id,
        "rich_message": {"blocks": blocks}
    }
    if reply_markup:
        if hasattr(reply_markup, "model_dump"):
            payload["reply_markup"] = reply_markup.model_dump(exclude_none=True)
        elif hasattr(reply_markup, "to_python"):
            payload["reply_markup"] = reply_markup.to_python()
        elif isinstance(reply_markup, dict):
            payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
            logger.debug(f"sendRichMessage returned {resp.status_code}: {resp.text}. Falling back to standard message.")
    except Exception as e:
        logger.debug(f"sendRichMessage request error: {e}. Falling back to standard message.")

    # Fallback to standard message
    return await bot.send_message(
        chat_id=chat_id,
        text=fallback_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2",
    )


async def edit_rich_msg(
    bot: Bot,
    chat_id: int,
    message_id: int,
    blocks: list,
    fallback_text: str,
    reply_markup: any = None,
) -> any:
    """Edits a message with Rich Message blocks, falling back to standard text edit"""
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload: dict = {
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": {"blocks": blocks}
    }
    if reply_markup:
        if hasattr(reply_markup, "model_dump"):
            payload["reply_markup"] = reply_markup.model_dump(exclude_none=True)
        elif hasattr(reply_markup, "to_python"):
            payload["reply_markup"] = reply_markup.to_python()
        elif isinstance(reply_markup, dict):
            payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass

    try:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=fallback_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2",
        )
    except Exception:
        pass


# Helper: get client for user with token decryption and auto-save on refresh
async def get_client(telegram_id: int) -> Optional[DnevnikClient]:
    user = await db.get_user(telegram_id)
    if not user or not user.get("access_token") or not user.get("refresh_token"):
        return None

    meta = user.get("meta", {})
    school_year = meta.get("school_year") or SCHOOL_YEAR

    async def on_refreshed(new_access: str, new_refresh: str):
        current_meta = user.get("meta", {})
        await db.save_tokens(telegram_id, new_access, new_refresh, meta=current_meta)
        logger.info(f"Updated refreshed tokens in database for user {telegram_id}")

    return DnevnikClient(
        access_token=user["access_token"],
        refresh_token=user["refresh_token"],
        school_year=school_year,
        on_token_refreshed=on_refreshed,
    )


# Helper: generate user reply buttons with personalized class name
async def get_reply_keyboard(telegram_id: int) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    user = await db.get_user(telegram_id)
    if not user or not user.get("access_token"):
        return ReplyKeyboardRemove()

    meta = user.get("meta", {})
    class_name = meta.get("className", "")
    if not class_name:
        try:
            client = await get_client(telegram_id)
            if client:
                p = await client.profile()
                class_name = p.get("className", "")
                if class_name:
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


async def send_login_prompt(bot: Bot, chat_id: int):
    webapp = WebAppInfo(url=WEBAPP_URL)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Регистрация", web_app=webapp)]],
        resize_keyboard=True,
    )
    await bot.send_message(
        chat_id=chat_id,
        text="Чтобы зарегистрироваться, нажмите кнопку снизу\\.\nТакже прочтите инструкцию внутри формы\\.",
        reply_markup=kb,
        parse_mode="MarkdownV2",
    )


async def send_grades_menu(bot: Bot, user_id: int, chat_id: int, message_id: Optional[int] = None):
    client = await get_client(user_id)
    if not client:
        await bot.send_message(chat_id, "Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    yr_display = f" (год: {client.school_year})" if client.school_year else ""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Текущая неделя", callback_data="wgrades")],
            [InlineKeyboardButton(text="1 четверть", callback_data="pgrades0"), InlineKeyboardButton(text="2 четверть", callback_data="pgrades1")],
            [InlineKeyboardButton(text="3 четверть", callback_data="pgrades2"), InlineKeyboardButton(text="4 четверть", callback_data="pgrades3")],
            [InlineKeyboardButton(text="По четвертям (Итог)", callback_data="ygrades")],
            [InlineKeyboardButton(text="🗓 Сменить учебный год", callback_data="select_year")],
        ]
    )
    text = f"Выберите период{yr_display}:"
    if message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb)
            return
        except Exception:
            pass
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)


async def send_year_selection(bot: Bot, user_id: int, chat_id: int, message_id: Optional[int] = None):
    client = await get_client(user_id)
    if not client:
        await bot.send_message(chat_id, "Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        years = await client.get_school_years()
        rows = []
        for y in years:
            y_id = y["id"]
            y_text = y["text"]
            mark = " ✅" if client.school_year == y_id else ""
            rows.append([InlineKeyboardButton(text=f"📚 {y_text}{mark}", callback_data=f"setyear_{y_id}")])
        rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_grades")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        text = (
            f"📅 Текущий активный учебный год: <b>{client.school_year or 'не задан'}</b>\n\n"
            "Выберите учебный год для просмотра расписания, оценок и домашних заданий:"
        )
        if message_id:
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb, parse_mode="HTML")
                return
            except Exception:
                pass
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error fetching school years: {e}")
        await bot.send_message(chat_id=chat_id, text="Не удалось загрузить список учебных лет.")


# -------------------------------------------------------------
# Base Command Handlers
# -------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("access_token"):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Регистрация", callback_data="reg")],
                [InlineKeyboardButton(text="📄 Список команд", callback_data="help")],
            ]
        )
        await message.answer(
            "Привет! 👋 Я бот для электронного школьного дневника Свердловской области.\n\n"
            "Чтобы начать пользоваться ботом, зарегистрируйтесь 👇",
            reply_markup=kb,
        )
    else:
        reply_kb = await get_reply_keyboard(message.from_user.id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📄 Список команд", callback_data="help")]]
        )
        await message.answer("С возвращением! Выберите действие:", reply_markup=reply_kb)
        await message.answer("Или посмотрите список команд:", reply_markup=kb)


@dp.message(Command("login"))
async def cmd_login(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("access_token"):
        await send_login_prompt(message.bot, message.chat.id)
    else:
        reply_kb = await get_reply_keyboard(message.from_user.id)
        await message.answer("Вы уже зарегистрированы", reply_markup=reply_kb)


@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        access_token = data.get("accessToken", "").strip()
        refresh_token = data.get("refreshToken", "").strip()

        if not access_token or not refresh_token:
            await message.answer("Ошибка: не были получены токены. Попробуйте еще раз.")
            return

        client = DnevnikClient(access_token=access_token, refresh_token=refresh_token, school_year=SCHOOL_YEAR)
        new_access, new_refresh = await client.refresh_tokens()

        # Fetch profile to store student details
        profile = await client.profile()
        meta = {
            "firstName": profile.get("firstName", ""),
            "lastName": profile.get("lastName", ""),
            "surName": profile.get("surName", ""),
            "className": profile.get("className", ""),
            "orgName": profile.get("orgName", ""),
            "school_year": client.school_year or SCHOOL_YEAR,
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
    await send_rich_msg(
        bot=message.bot,
        chat_id=message.from_user.id,
        blocks=rf.rich_help(),
        fallback_text=format_help_message(),
        reply_markup=reply_kb,
    )


@dp.message(Command("calls"))
async def cmd_calls(message: Message):
    await send_rich_msg(
        bot=message.bot,
        chat_id=message.from_user.id,
        blocks=rf.rich_calls(),
        fallback_text=format_calls_message(),
    )


@dp.message(Command("year"))
@dp.message(Command("setyear"))
async def cmd_year(message: Message):
    await send_year_selection(message.bot, message.from_user.id, message.chat.id)


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    client = await get_client(user_id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        p = await client.profile()
        user = await db.get_user(user_id)
        meta = (user or {}).get("meta", {})
        active_year = meta.get("school_year") or client.school_year or "текущий"
        active_class = meta.get("className") or p.get("className", "")

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🗓 Сменить учебный год", callback_data="select_year")],
                [InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data="deleteacc_prompt")],
            ]
        )
        res = (
            f"👤 <b>{p.get('lastName', '')} {p.get('firstName', '')} {p.get('surName', '')}</b>\n"
            f"🏫 {p.get('orgName', '')}\n"
            f"🎒 Класс: <b>{active_class}</b>\n"
            f"📅 Учебный год: <b>{active_year}</b>\n\n"
            "Сменить учебный год — /year\n"
            "Удалить аккаунт — /delacc"
        )
        await message.answer(res, reply_markup=kb, parse_mode="HTML")
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
    chat_id = message_or_query.message.chat.id if isinstance(message_or_query, CallbackQuery) else message_or_query.chat.id
    client = await get_client(user_id)
    bot = message_or_query.bot

    if not client:
        await bot.send_message(chat_id, "Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        lessons = await client.schedule(day_idx)
        blocks = rf.rich_schedule(day_idx, lessons)
        fallback = format_schedule_message(day_idx, lessons)
        await send_rich_msg(bot, chat_id, blocks, fallback)
    except Exception as e:
        logger.error(f"Schedule error: {e}")
        await bot.send_message(chat_id, "Не удалось загрузить расписание.")


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
    await message.answer("Выберите день недели:", reply_markup=kb)


# -------------------------------------------------------------
# Grades Handlers
# -------------------------------------------------------------

@dp.message(Command("grades"))
@dp.message(F.text == "📋 Все оценки")
async def cmd_grades(message: Message):
    await send_grades_menu(message.bot, message.from_user.id, message.chat.id)


@dp.message(Command("wgrades"))
@dp.message(F.text.contains("на этой неделе"))
async def cmd_wgrades(message: Message):
    client = await get_client(message.from_user.id)
    if not client:
        await message.answer("Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        gr = await client.grades_week()
        blocks = rf.rich_week_grades(gr)
        fallback = format_week_grades_message(gr)
        await send_rich_msg(message.bot, message.from_user.id, blocks, fallback)
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
        blocks = rf.rich_year_grades(year_grades)
        fallback = format_year_grades_message(year_grades)
        reply_kb = await get_reply_keyboard(message.from_user.id)
        await send_rich_msg(message.bot, message.from_user.id, blocks, fallback, reply_markup=reply_kb)
    except Exception as e:
        logger.error(f"Year grades error: {e}")
        await message.answer("Не удалось получить четвертные оценки.")


async def send_period_grades(message_or_query: Message | CallbackQuery, period_idx: int):
    user_id = message_or_query.from_user.id
    chat_id = message_or_query.message.chat.id if isinstance(message_or_query, CallbackQuery) else message_or_query.chat.id
    client = await get_client(user_id)
    bot = message_or_query.bot

    if not client:
        await bot.send_message(chat_id, "Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        return

    try:
        disciplines = await client.grades_period(period_idx)
        blocks = rf.rich_period_grades(period_idx + 1, disciplines)
        fallback = format_period_grades_message(period_idx + 1, disciplines)
        reply_kb = await get_reply_keyboard(user_id)
        await send_rich_msg(bot, chat_id, blocks, fallback, reply_markup=reply_kb)
    except Exception as e:
        logger.error(f"Period grades error: {e}")
        await bot.send_message(chat_id, "Не удалось получить оценки за четверть.")


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
        blocks = rf.rich_homework(hw_data)
        fallback = format_homework_message(hw_data)
        kb = build_hw_keyboard(hw_data.get("pages", {}))
        await send_rich_msg(message.bot, message.from_user.id, blocks, fallback, reply_markup=kb)
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
    chat_id = query.message.chat.id
    bot = query.bot
    client = await get_client(user_id)

    if data == "reg":
        await send_login_prompt(bot, chat_id)
        await query.answer()
        return

    if data == "help":
        reply_kb = await get_reply_keyboard(user_id)
        await send_rich_msg(bot, chat_id, rf.rich_help(), format_help_message(), reply_markup=reply_kb)
        await query.answer()
        return

    if data == "deleteacc_prompt":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Да, удалить", callback_data="deleteacc1"),
                    InlineKeyboardButton(text="Нет, отмена", callback_data="deleteacc0"),
                ]
            ]
        )
        await bot.send_message(chat_id=chat_id, text="Вы действительно хотите удалить аккаунт?", reply_markup=kb)
        await query.answer()
        return

    if not client:
        await bot.send_message(chat_id=chat_id, text="Вы не зарегистрированы", reply_markup=get_unreg_keyboard())
        await query.answer()
        return

    if data == "select_year":
        await send_year_selection(bot, user_id, chat_id, message_id=query.message.message_id)

    elif data.startswith("setyear_"):
        chosen_year = data.split("_", 1)[1]
        user = await db.get_user(user_id)
        if user:
            meta = user.get("meta", {})
            meta["school_year"] = chosen_year

            # Try to resolve class name for the chosen year to update reply keyboard
            try:
                temp_client = DnevnikClient(user["access_token"], user["refresh_token"], school_year=chosen_year)
                await temp_client.init_ids()
                if temp_client.class_name:
                    meta["className"] = temp_client.class_name
            except Exception as cls_err:
                logger.warning(f"Could not resolve class name for year {chosen_year}: {cls_err}")

            await db.save_tokens(user_id, user["access_token"], user["refresh_token"], meta=meta)
            await query.answer(f"Выбран {chosen_year} учебный год!", show_alert=True)

            try:
                await query.message.delete()
            except Exception:
                pass

            reply_kb = await get_reply_keyboard(user_id)
            cls_info = f" (класс: {meta.get('className')})" if meta.get('className') else ""
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Учебный год успешно переключен на <b>{chosen_year}</b>{cls_info}.\nТеперь расписание, оценки и ДЗ отображаются для этого года.",
                reply_markup=reply_kb,
                parse_mode="HTML",
            )

    elif data == "back_to_grades":
        await send_grades_menu(bot, user_id, chat_id, message_id=query.message.message_id)

    elif data.startswith("schedule"):
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
            await bot.send_message(chat_id=chat_id, text="Ваш аккаунт удален", reply_markup=kb)
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
            blocks = rf.rich_week_grades(gr)
            fallback = format_week_grades_message(gr)
            await send_rich_msg(bot, chat_id, blocks, fallback)
        except Exception as e:
            logger.error(f"Week grades error: {e}")
            await bot.send_message(chat_id=chat_id, text="Не удалось получить оценки за неделю.")

    elif data == "ygrades":
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            year_grades = await client.grades_year()
            blocks = rf.rich_year_grades(year_grades)
            fallback = format_year_grades_message(year_grades)
            reply_kb = await get_reply_keyboard(user_id)
            await send_rich_msg(bot, chat_id, blocks, fallback, reply_markup=reply_kb)
        except Exception as e:
            logger.error(f"Year grades error: {e}")
            await bot.send_message(chat_id=chat_id, text="Не удалось получить четвертные оценки.")

    elif data.startswith("hw"):
        code = data[2:]
        if code == "noop":
            await query.answer("Дальше заданий нет", show_alert=False)
            return

        date_str = None if code == "today" else code
        try:
            hw_data = await client.homework(date_str)
            blocks = rf.rich_homework(hw_data)
            fallback = format_homework_message(hw_data)
            kb = build_hw_keyboard(hw_data.get("pages", {}))
            await edit_rich_msg(bot, chat_id, query.message.message_id, blocks, fallback, reply_markup=kb)
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
        BotCommand(command="pgrades", description="📋 Оценки по четвертям"),
        BotCommand(command="homework", description="✍️ Домашнее задание"),
        BotCommand(command="year", description="🗓 Сменить учебный год"),
        BotCommand(command="calls", description="🔔 Расписание звонков"),
        BotCommand(command="profile", description="👤 Профиль ученика"),
        BotCommand(command="help", description="📄 Список команд"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")


async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set in .env! Please set it and restart.")
        sys.exit(1)

    logger.info("Initializing database...")
    await db.init_db()

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await set_my_commands(bot)

    # Start background token refresher loop
    refresher_task = asyncio.create_task(run_tokens_refresher_loop())

    # Start WebApp static server if enabled
    if ENABLE_WEBAPP_SERVER:
        try:
            await run_webapp_server(host=WEBAPP_HOST, port=WEBAPP_PORT)
        except Exception as e:
            logger.error(f"Failed to start WebApp server: {e}")

    logger.info("Bot started successfully. Polling updates...")
    try:
        await dp.start_polling(bot)
    finally:
        refresher_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
