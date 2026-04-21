from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from db import get_orders
from keyboards import main_menu

router = Router()


@router.message(Command("history", prefix="/."))
@router.message(F.text == "📋 History")
async def show_history(message: Message):
    orders = await get_orders(message.from_user.id, limit=10)

    if not orders:
        await message.answer(
            "📋 *Order History*\n\nYou have no orders yet.\n\nUse *Place Order* to get started!",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    text = "📋 *Your Recent Orders*\n\n"
    for order in orders:
        status_emoji = {"success": "✅", "failed": "❌", "processing": "⏳", "pending": "🕐"}.get(
            order["status"], "❓"
        )
        date = order["created_at"][:10] if order["created_at"] else "N/A"
        text += f"{status_emoji} *Order #{order['id']}*\n"
        text += f"   📧 `{order['gmail']}`\n"
        text += f"   Status: {order['status'].capitalize()}\n"
        text += f"   Date: {date}\n"
        if order.get("generated_link"):
            text += f"   🔗 [Link]({order['generated_link']})\n"
        text += "\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(), disable_web_page_preview=True)
