from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Place Order"), KeyboardButton(text="💰 Balance")],
            [KeyboardButton(text="🎁 Refer & Earn"), KeyboardButton(text="📋 History")],
            [KeyboardButton(text="📞 Contact Support"), KeyboardButton(text="📖 Guide")],
        ],
        resize_keyboard=True,
    )


def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/cancel")]],
        resize_keyboard=True,
    )


def admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="➕ Add Balance", callback_data="admin_add_bal")],
            [InlineKeyboardButton(text="➖ Deduct Balance", callback_data="admin_deduct_bal")],
            [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban")],
            [InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban")],
        ]
    )


def confirm_order_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_order"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order"),
            ]
        ]
    )
