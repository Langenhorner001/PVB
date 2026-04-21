from aiogram import Router, F
from aiogram.types import Message
from aiogram import Bot
from db import get_user, get_referral_count
from keyboards import main_menu
from config import REFERRAL_REWARD

router = Router()

_BOT_USERNAME: str | None = None


async def _get_bot_username(bot: Bot) -> str:
    global _BOT_USERNAME
    if _BOT_USERNAME is None:
        me = await bot.get_me()
        _BOT_USERNAME = me.username
    return _BOT_USERNAME


@router.message(F.text == "🎁 Refer & Earn")
async def show_referral(message: Message, bot: Bot):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return

    ref_count = await get_referral_count(message.from_user.id)
    bot_username = await _get_bot_username(bot)
    ref_link = f"https://t.me/{bot_username}?start={user['referral_code']}"

    await message.answer(
        f"🎁 *Refer & Earn Program*\n\n"
        f"Share your referral link and earn *{REFERRAL_REWARD} credits* for every new user who joins!\n\n"
        f"🔗 *Your Referral Link:*\n`{ref_link}`\n\n"
        f"👥 *Total Referrals:* {ref_count}\n"
        f"💰 *Earned:* {ref_count * REFERRAL_REWARD} credits\n\n"
        f"Share this link with your friends and start earning! 🚀",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
