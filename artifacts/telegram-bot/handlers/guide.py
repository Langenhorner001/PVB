from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from keyboards import main_menu

router = Router()


@router.message(Command("guide"))
@router.message(F.text == "📖 Guide")
async def show_guide(message: Message):
    guide_text = (
        "📖 *How to Use This Bot*\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "*Step 1:* Tap *🛒 Place Order*\n"
        "→ Bot will ask for your Gmail address\n\n"
        "*Step 2:* Enter your Gmail\n"
        "→ Example: `yourname@gmail.com`\n\n"
        "*Step 3:* Enter your Google password\n"
        "→ The password you use to login to Gmail\n\n"
        "*Step 4:* Enter your 2FA Secret Key\n"
        "→ This is the *secret key* from your authenticator app\n"
        "→ NOT the 6-digit code — the secret key used to set it up\n"
        "→ Usually looks like: `JBSWY3DPEHPK3PXP`\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "*After Order:*\n"
        "✅ You'll receive a unique Google One partner link\n\n"
        "⚠️ *IMPORTANT:*\n"
        "• Open the link in a browser where *only that Gmail* is logged in\n"
        "• Sign out all other Google accounts first\n"
        "• Otherwise you'll get the *\"Can't redeem offer\"* error\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "💰 *Credits:*\n"
        "• Each order costs `40` credits\n"
        "• Earn `10` credits per referral\n\n"
        "❓ Still confused? Contact *📞 Contact Support*"
    )
    await message.answer(guide_text, parse_mode="Markdown", reply_markup=main_menu())
