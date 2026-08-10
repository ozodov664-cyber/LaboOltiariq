"""Mini app veb-server: statik fayllarni (webapp/) va /api/* endpoint'larini xizmat qiladi.
Bot polling bilan bir xil asyncio jarayonida, bir xil SQLite bazasidan foydalanib ishlaydi."""
import os

from aiohttp import web

import api_client
import api_driver
import api_dispatcher
import api_admin

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")


async def health(request):
    return web.json_response({"ok": True, "service": "labooltiariq-webapp"})


@web.middleware
async def no_cache_middleware(request, handler):
    """Mini-app frontend (index.html, /static/*) doim eng so'nggi versiyada yuklansin —
    Telegram'ning ichki WebView'i (ayniqsa iOS'da) statik fayllarni juda qattiq keshlab
    qo'yadi, shu sabab yangi deploy qilingandan keyin ham eski JS/CSS ko'rsatilib qolib,
    tugmalar "ishlamay qolgan" ko'rinishga olib kelishi mumkin edi. API javoblariga
    tegilmaydi — faqat frontend fayllariga."""
    response = await handler(request)
    if request.path == "/" or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def create_app(bot) -> web.Application:
    app = web.Application(middlewares=[no_cache_middleware])
    app["bot"] = bot

    app.router.add_get("/health", health)
    app.add_routes(api_client.routes)
    app.add_routes(api_driver.routes)
    app.add_routes(api_dispatcher.routes)
    app.add_routes(api_admin.routes)

    # Mini app frontend (statik fayllar) — /webapp/ papkasidan
    if os.path.isdir(WEBAPP_DIR):
        app.router.add_static("/static/", WEBAPP_DIR, show_index=False)

        async def index(request):
            return web.FileResponse(os.path.join(WEBAPP_DIR, "index.html"))

        app.router.add_get("/", index)
        # SPA: noma'lum GET yo'llar ham index.html'ga (front-end o'zi routing qiladi)
        app.router.add_get("/{tail:(?!api/|static/|health).*}", index)

    return app


async def run_web_app(bot):
    port = int(os.environ.get("PORT", "8080"))
    app = create_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    return runner
