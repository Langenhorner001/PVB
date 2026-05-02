import asyncio
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS, BOT_NAME
from db import init_db
from auth_middleware import BanCheckMiddleware
from throttle_middleware import ThrottleMiddleware

import start, order, balance, history, referral, guide, contact, admin, topup, system, proxy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def notify_admins_startup(bot: Bot) -> None:
    if not ADMIN_IDS:
        logger.warning("No ADMIN_IDS configured; startup notification skipped.")
        return

    try:
        me = await bot.get_me()
        bot_label = f"@{me.username}" if me.username else BOT_NAME
    except Exception:
        bot_label = BOT_NAME

    text = (
        "╔══════════════════════╗\n"
        "   🟢 *BOT IS LIVE AGAIN*\n"
        "╚══════════════════════╝\n\n"
        "🚀 *Pixel Verification Bot restarted successfully!*\n\n"
        f"🤖 *Bot:* `{bot_label}`\n"
        "📡 *Mode:* `Long polling active`\n"
        "💾 *Database:* `Connected`\n"
        f"🕒 *Started At:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
        "✅ *Status:* `Online and ready to process orders`\n\n"
        "_Admin alert only. Users were not notified._"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            logger.warning("Failed to send startup notification to admin %s: %s", admin_id, exc)


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please add it to your .env file or secrets store.")
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
    dp.include_router(proxy.router)
    dp.include_router(admin.router)

    logger.info("Bot is starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await notify_admins_startup(bot)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
