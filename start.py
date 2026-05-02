from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from db import get_or_create_user
from keyboards import main_menu
from config import BOT_NAME, INITIAL_BALANCE

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None

    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "User",
        ref_code=ref_code,
    )

    welcome = (
        f"👋 *Welcome to {BOT_NAME}!*\n\n"
        f"🔥 Generate Google One Partner EFT Onboard links instantly.\n\n"
        f"📌 *How it works:*\n"
        f"1️⃣ Place an order — provide your Google login details\n"
        f"2️⃣ Bot generates your unique Google One partner link\n"
        f"3️⃣ Open the link *only* in the browser where that Gmail is logged in\n\n"
        f"💰 *Your Balance:* `{user['balance']}` credits\n\n"
        f"Use the menu below to get started 👇"
    )

    await message.answer(welcome, parse_mode="Markdown", reply_markup=main_menu())
