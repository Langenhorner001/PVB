from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from db import get_orders, get_transactions
from keyboards import main_menu

router = Router()


_MD_SPECIALS = r"_*`["


def _md_escape(text: str) -> str:
    if not text:
        return ""
    out = []
    for ch in str(text):
        if ch in _MD_SPECIALS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def _format_tx_amount(amount: int) -> str:
    sign = "+" if amount >= 0 else "−"
    return f"{sign}{abs(amount)}"


def _tx_emoji(tx_type: str, amount: int) -> str:
    t = (tx_type or "").lower()
    if "topup" in t or "top_up" in t or "top-up" in t:
        return "💎"
    if "referral" in t:
        return "🎁"
    if "refund" in t:
        return "↩️"
    if "order" in t or "spend" in t or "deduct" in t:
        return "🛒"
    return "➕" if amount >= 0 else "➖"


@router.message(Command("history", prefix="/."))
@router.message(F.text == "📋 History")
async def show_history(message: Message):
    orders = await get_orders(message.from_user.id, limit=10)
    transactions = await get_transactions(message.from_user.id, limit=10)

    if not orders and not transactions:
        await message.answer(
            "📋 *History*\n\nYou have no orders or transactions yet.\n\nUse *Place Order* or *Top Up* to get started!",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    text = "📋 *Your Recent Activity*\n\n"

    if orders:
        text += "🛒 *Recent Orders*\n\n"
        for order in orders:
            status_emoji = {"success": "✅", "failed": "❌", "processing": "⏳", "pending": "🕐"}.get(
                order["status"], "❓"
            )
            date = order["created_at"][:10] if order["created_at"] else "N/A"
            text += f"{status_emoji} *Order #{order['id']}*\n"
            text += f"   📧 `{_md_escape(order['gmail'])}`\n"
            text += f"   Status: {order['status'].capitalize()}\n"
            text += f"   Date: {date}\n"
            if order.get("generated_link"):
                text += f"   🔗 `{_md_escape(order['generated_link'])}`\n"
            text += "\n"

    if transactions:
        text += "💳 *Recent Credit Transactions*\n\n"
        for tx in transactions:
            amount = tx.get("amount") or 0
            tx_type = tx.get("type") or "transaction"
            emoji = _tx_emoji(tx_type, amount)
            date = tx["created_at"][:10] if tx.get("created_at") else "N/A"
            type_label = _md_escape(tx_type.replace("_", " ").title())
            text += f"{emoji} *{type_label}* `{_format_tx_amount(amount)}`\n"
            if tx.get("description"):
                text += f"   {_md_escape(tx['description'])}\n"
            text += f"   Date: {date}\n\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu(), disable_web_page_preview=True)
