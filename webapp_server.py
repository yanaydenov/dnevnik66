import logging
import urllib.parse
import json
from typing import Optional
from aiohttp import web
from aiogram import Bot
from pathlib import Path
from config import BASE_DIR, WEBAPP_HOST, WEBAPP_PORT, SCHOOL_YEAR

logger = logging.getLogger(__name__)

bot_instance: Optional[Bot] = None


def set_bot_instance(bot: Bot):
    global bot_instance
    bot_instance = bot


async def login_handler(request: web.Request) -> web.Response:
    login_page = BASE_DIR / "static" / "loginPage.html"
    if login_page.exists():
        return web.FileResponse(login_page)
    return web.Response(text="Login page not found", status=404)


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "dnevnik-bot"})


async def api_login_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Неверный формат запроса"}, status=400)

    access_token = str(data.get("accessToken", "")).strip()
    refresh_token = str(data.get("refreshToken", "")).strip()
    user_id = data.get("userId")
    init_data = data.get("initData", "")

    # Parse user_id from initData if not provided directly
    if not user_id and init_data:
        parsed = urllib.parse.parse_qs(init_data)
        user_json_str = parsed.get("user", [""])[0]
        if user_json_str:
            try:
                user_obj = json.loads(user_json_str)
                user_id = user_obj.get("id")
            except Exception:
                pass

    if not access_token or not refresh_token:
        return web.json_response({"success": False, "error": "Токены не могут быть пустыми"}, status=400)

    if not user_id:
        return web.json_response({"success": False, "error": "Не удалось определить пользователя. Откройте приложение внутри Telegram."}, status=400)

    try:
        user_id = int(user_id)
        import database as db
        from dnevnik_client import DnevnikClient
        import rich_formatters as rf

        client = DnevnikClient(access_token=access_token, refresh_token=refresh_token, school_year=SCHOOL_YEAR)
        new_access, new_refresh = await client.refresh_tokens()
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

        if bot_instance:
            from bot import get_reply_keyboard, send_rich_msg
            reply_kb = await get_reply_keyboard(user_id)
            blocks = rf.rich_start(is_registered=True, student_name=profile.get("firstName", ""))
            fallback = "Вы успешно зарегистрировались!"
            await send_rich_msg(bot_instance, user_id, blocks, fallback, reply_markup=reply_kb)

        return web.json_response({"success": True, "studentName": profile.get("firstName", "")})

    except Exception as e:
        logger.error(f"API Login error: {e}")
        return web.json_response({"success": False, "error": f"Ошибка авторизации: {e}"}, status=400)


def create_webapp_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", login_handler)
    app.router.add_get("/login", login_handler)
    app.router.add_post("/api/login", api_login_handler)
    app.router.add_get("/health", health_handler)

    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.router.add_static("/static/", path=str(static_dir), name="static")

    return app


async def run_webapp_server(host: str = WEBAPP_HOST, port: int = WEBAPP_PORT, bot: Optional[Bot] = None):
    if bot:
        set_bot_instance(bot)
    app = create_webapp_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    logger.info(f"Starting built-in WebApp server on http://{host}:{port}/login")
    await site.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_webapp_app()
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
