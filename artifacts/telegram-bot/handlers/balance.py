from aiogram import Router, F
from aiogram.types import Message
from db import get_user
from keyboards import main_menu

router = Router()


@router.message(F.text == "💰 Balance")
async def show_balance(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return

    await message.answer(
        f"💰 *Your Balance*\n\n"
        f"Available Credits: `{user['balance']}`\n\n"
        f"Use *Place Order* to generate Google One partner links.\n"
        f"Each order costs `40` credits.\n\n"
        f"Earn credits by referring friends! 🎁",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
