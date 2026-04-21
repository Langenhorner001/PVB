from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from db import get_user
from keyboards import main_menu
from config import ORDER_COST

router = Router()


def _balance_inline_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Top-Up Credits", callback_data="open_topup")]
        ]
    )


@router.message(F.text == "💰 Balance")
async def show_balance(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return

    orders_possible = user["balance"] // ORDER_COST
    await message.answer(
        f"💰 *Your Balance*\n\n"
        f"Available Credits: `{user['balance']}`\n"
        f"Orders You Can Place: `{orders_possible}`\n\n"
        f"Each order costs `{ORDER_COST}` credits.\n\n"
        f"Top up to get more credits, or earn them by referring friends! 🎁",
        parse_mode="Markdown",
        reply_markup=_balance_inline_kb(),
    )
