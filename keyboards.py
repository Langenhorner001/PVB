from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOPUP_PACKAGES

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Place Order"), KeyboardButton(text="💰 Balance")],
            [KeyboardButton(text="💳 Top-Up"), KeyboardButton(text="🎁 Refer & Earn")],
            [KeyboardButton(text="📋 History"), KeyboardButton(text="📖 Guide")],
            [KeyboardButton(text="📞 Contact Support")],
        ],
        resize_keyboard=True,
    )


def topup_method_choice_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Telegram Stars (Instant)", callback_data="open_stars_topup")],
            [InlineKeyboardButton(text="📱 Easypaisa / JazzCash (Manual)", callback_data="open_manual_topup")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="topup_cancel")],
        ]
    )


def topup_amounts_kb(amounts):
    rows = []
    row = []
    for amt in amounts:
        row.append(InlineKeyboardButton(text=f"💰 {amt}", callback_data=f"topup_amt:{amt}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✏️ Custom Amount", callback_data="topup_amt:custom")])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="topup_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_method_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Easypaisa", callback_data="topup_method:easypaisa")],
            [InlineKeyboardButton(text="📱 JazzCash", callback_data="topup_method:jazzcash")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="topup_cancel")],
        ]
    )


def topup_admin_kb(request_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"topup_approve:{request_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"topup_reject:{request_id}"),
            ]
        ]
    )


def topup_packages_kb():
    buttons = []
    for pkg in TOPUP_PACKAGES:
        buttons.append([
            InlineKeyboardButton(
                text=f"{pkg['emoji']} {pkg['label']} — {pkg['stars']} ⭐",
                callback_data=pkg["id"],
            )
        ])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="topup_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/cancel")]],
        resize_keyboard=True,
    )


def admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💰 Top-Up Revenue", callback_data="admin_revenue")],
            [InlineKeyboardButton(text="📦 Orders", callback_data="admin_orders")],
            [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="➕ Add Balance", callback_data="admin_add_bal")],
            [InlineKeyboardButton(text="➖ Deduct Balance", callback_data="admin_deduct_bal")],
            [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban")],
            [InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban")],
        ]
    )


def admin_revenue_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Export CSV", callback_data="admin_revenue_export")],
            [InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_back")],
        ]
    )


def admin_order_kb(order_id: int, status: str):
    buttons = []
    if status != "success":
        buttons.append([InlineKeyboardButton(text="✅ Mark Successful", callback_data=f"admin_order_success:{order_id}")])
    if status not in ("refunded",):
        buttons.append([InlineKeyboardButton(text="💸 Issue Refund", callback_data=f"admin_order_refund:{order_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Back to Orders", callback_data="admin_orders")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_orders_list_kb(orders: list):
    buttons = []
    for o in orders:
        status_icon = {"success": "✅", "failed": "❌", "processing": "⏳", "refunded": "💸"}.get(o["status"], "❓")
        label = f"{status_icon} #{o['id']} — {o['gmail'][:20]}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"admin_order_detail:{o['id']}")])
    buttons.append([InlineKeyboardButton(text="🔍 Search Orders", callback_data="admin_order_search")])
    buttons.append([InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_order_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_order"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order"),
            ]
        ]
    )
