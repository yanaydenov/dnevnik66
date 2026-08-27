import logging
from aiohttp import web
from pathlib import Path
from config import BASE_DIR, WEBAPP_HOST, WEBAPP_PORT

logger = logging.getLogger(__name__)


async def login_handler(request: web.Request) -> web.Response:
    login_page = BASE_DIR / "static" / "loginPage.html"
    if login_page.exists():
        return web.FileResponse(login_page)
    return web.Response(text="Login page not found", status=404)


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "dnevnik-bot"})


def create_webapp_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", login_handler)
    app.router.add_get("/login", login_handler)
    app.router.add_get("/health", health_handler)

    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.router.add_static("/static/", path=str(static_dir), name="static")

    return app


async def run_webapp_server(host: str = WEBAPP_HOST, port: int = WEBAPP_PORT):
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
