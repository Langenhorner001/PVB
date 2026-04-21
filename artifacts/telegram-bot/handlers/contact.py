from aiogram import Router, F
from aiogram.types import Message
from keyboards import main_menu
from config import SUPPORT_USERNAME

router = Router()


@router.message(F.text == "📞 Contact Support")
async def show_contact(message: Message):
    await message.answer(
        f"📞 *Contact Support*\n\n"
        f"Having issues? We're here to help!\n\n"
        f"👤 Support: {SUPPORT_USERNAME}\n\n"
        f"📝 *Common Issues:*\n"
        f"• Order failed → Check your credentials\n"
        f"• Link not working → Sign out other Google accounts first\n"
        f"• Balance issue → Contact support with your User ID\n\n"
        f"🆔 *Your User ID:* `{message.from_user.id}`\n\n"
        f"Please include your User ID when contacting support.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
