import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from db import init_db
from auth_middleware import BanCheckMiddleware
from throttle_middleware import ThrottleMiddleware

import start, order, balance, history, referral, guide, contact, admin, topup, system

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please add it to Replit Secrets.")
        return

    await init_db()
    logger.info("Database initialized.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(BanCheckMiddleware())
    dp.message.middleware(ThrottleMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())

    dp.include_router(start.router)
    dp.include_router(order.router)
    dp.include_router(balance.router)
    dp.include_router(topup.router)
    dp.include_router(history.router)
    dp.include_router(referral.router)
    dp.include_router(guide.router)
    dp.include_router(contact.router)
    dp.include_router(system.router)
    dp.include_router(admin.router)

    logger.info("Bot is starting...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
