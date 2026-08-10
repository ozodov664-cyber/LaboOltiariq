import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import db
import handlers_client
import handlers_driver
import handlers_dispatcher
import handlers_admin
import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")


async def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN topilmadi. .env faylida yoki muhit o'zgaruvchisida BOT_TOKEN=... ni belgilang.\n"
            "Tokenni @BotFather dan olasiz."
        )

    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(handlers_client.router)
    dp.include_router(handlers_driver.router)
    dp.include_router(handlers_dispatcher.router)
    dp.include_router(handlers_admin.router)

    await bot.delete_webhook(drop_pending_updates=True)

    # Mini app (webapp/) va /api/* endpoint'larini xizmat qiluvchi HTTP server — bot bilan
    # bir xil jarayonda, bir xil bazadan foydalanib, parallel ishlaydi.
    runner = await web.run_web_app(bot)
    logging.info("Mini app HTTP server ishga tushdi (port %s)", os.environ.get("PORT", "8080"))

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
