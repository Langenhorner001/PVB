import asyncio
import functools
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from db import (
    get_user,
    deduct_balance,
    add_balance,
    create_order,
    update_order,
    get_random_user_proxy,
    list_user_proxies,
    count_recent_failures_by_reason,
)
from keyboards import main_menu, cancel_kb, confirm_order_kb
from google_auth import google_login_and_get_link, R_SIGNIN_REJECTED
import re as _re
from helpers import escape_md
from config import ORDER_COST, ADMIN_IDS

# After this many recent SIGNIN_REJECTED failures with no proxy configured,
# the bot nudges the user to set a proxy.
PROXY_HINT_THRESHOLD = 3
PROXY_HINT_WINDOW_HOURS = 24

router = Router()
logger = logging.getLogger(__name__)


async def _delete_sensitive_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


class OrderState(StatesGroup):
    waiting_gmail = State()
    waiting_password = State()
    waiting_2fa = State()
    confirming = State()


@router.message(F.text == "🛒 Place Order")
async def place_order_start(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return

    is_admin = message.from_user.id in ADMIN_IDS
    if not is_admin and user["balance"] < ORDER_COST:
        topup_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Top-Up Now", callback_data="open_topup")]
            ]
        )
        await message.answer(
            f"❌ *Insufficient Balance!*\n\n"
            f"💰 Your balance: `{user['balance']}` credits\n"
            f"💵 Order cost: `{ORDER_COST}` credits\n\n"
            f"Top-up your balance to continue.",
            parse_mode="Markdown",
            reply_markup=topup_kb,
        )
        return

    await state.set_state(OrderState.waiting_gmail)
    await message.answer(
        f"🛒 *New Order — Step 1 of 3*\n\n"
        f"📧 Please enter your *Gmail address*:\n\n"
        f"_(Type /cancel to stop)_",
        parse_mode="Markdown",
        reply_markup=cancel_kb(),
    )


@router.message(Command("cancel", prefix="/."))
async def cancel_order(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ Order cancelled.", reply_markup=main_menu())
    else:
        await message.answer("Nothing to cancel.", reply_markup=main_menu())


@router.message(OrderState.waiting_gmail)
async def got_gmail(message: Message, state: FSMContext):
    email = (message.text or "").strip()
    if not email:
        await message.answer("⚠️ Please enter a Gmail address.")
        return
    if "@" not in email or "." not in email:
        await message.answer("⚠️ Invalid email. Please enter a valid Gmail address:")
        return
    await state.update_data(gmail=email)
    await state.set_state(OrderState.waiting_password)
    await message.answer(
        f"✅ Gmail: `{escape_md(email)}`\n\n"
        f"🔒 *Step 2 of 3* — Enter your *Google account password*:\n\n"
        f"_(Type /cancel to stop)_",
        parse_mode="Markdown",
    )


@router.message(OrderState.waiting_password)
async def got_password(message: Message, state: FSMContext):
    password = (message.text or "").strip()
    if not password:
        await message.answer("⚠️ Please enter your password.")
        return
    if len(password) < 6:
        await message.answer("⚠️ Password too short. Please enter your correct password:")
        return
    await state.update_data(password=password)
    await _delete_sensitive_message(message)
    await state.set_state(OrderState.waiting_2fa)
    await message.answer(
        f"🔐 *Step 3 of 3* — Enter your *2FA credential*:\n\n"
        f"• *TOTP secret key* from your authenticator app\n"
        f"  (e.g., `JBSWY3DPEHPK3PXP`)\n\n"
        f"• *or* a Google *backup code* (8 digits, e.g., `12345678`)\n\n"
        f"_(Type /cancel to stop)_",
        parse_mode="Markdown",
    )


async def _maybe_proxy_hint(user_id: int, reason_code: str) -> str:
    """Return a Markdown hint string when a user keeps hitting SIGNIN_REJECTED
    without any proxy configured. Empty string otherwise."""
    if reason_code != R_SIGNIN_REJECTED:
        return ""
    proxies = await list_user_proxies(user_id)
    if proxies:
        return ""
    fail_count = await count_recent_failures_by_reason(
        user_id, R_SIGNIN_REJECTED, hours=PROXY_HINT_WINDOW_HOURS
    )
    if fail_count < PROXY_HINT_THRESHOLD:
        return ""
    return (
        "🌐 *Tip:* Bhai, bot ki IP Google ne flag ki lagti hai "
        f"(pichle {PROXY_HINT_WINDOW_HOURS}h mein `{fail_count}` baar reject hua hai). "
        "Ek *residential / mobile proxy* `/setproxy` se laga ke try karo — "
        "kaafi accounts is ke baad chal jate hain.\n\n"
    )


def _parse_2fa_input(raw: str):
    """
    Detect whether the user entered a TOTP secret or a Google backup code.

    Google backup codes are exactly 8 digits (spaces/dashes allowed).
    Everything else is treated as a TOTP secret.

    Returns (totp_secret, backup_code) where one of them will be None.
    """
    clean = raw.strip().replace(" ", "").replace("-", "")
    if _re.fullmatch(r"[0-9]{8}", clean):
        return None, clean
    return raw.strip(), None


@router.message(OrderState.waiting_2fa)
async def got_2fa(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("⚠️ Please enter your 2FA secret or backup code.")
        return
    totp_secret, backup_code = _parse_2fa_input(raw)

    if totp_secret is None and backup_code is None:
        await message.answer("⚠️ Input not recognised. Please enter your 2FA secret or an 8-digit backup code:")
        return

    if totp_secret is not None and len(totp_secret.replace(" ", "")) < 8:
        await message.answer("⚠️ 2FA secret seems too short. Please check and re-enter:")
        return

    await state.update_data(totp_secret=totp_secret, backup_code=backup_code)
    await _delete_sensitive_message(message)
    data = await state.get_data()
    await state.set_state(OrderState.confirming)

    if backup_code:
        cred_line = f"🔐 2FA: backup code `{backup_code[:4]}****`"
    else:
        cred_line = f"🔐 2FA Secret: `{totp_secret[:4]}...`"

    await message.answer(
        f"📋 *Order Summary*\n\n"
        f"📧 Gmail: `{escape_md(data['gmail'])}`\n"
        f"🔑 Password: `{'*' * len(data['password'])}`\n"
        f"{cred_line}\n\n"
        f"💵 Cost: `{ORDER_COST}` credits\n\n"
        f"Confirm your order?",
        parse_mode="Markdown",
        reply_markup=confirm_order_kb(),
    )


@router.callback_query(F.data == "cancel_order")
async def cb_cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Order cancelled.")
    await callback.message.answer("Back to menu:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "confirm_order")
async def cb_confirm_order(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    if not data or "gmail" not in data:
        await callback.message.edit_text("⚠️ Session expired. Please start a new order.")
        await callback.answer()
        return

    await state.clear()

    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not user:
        await callback.message.edit_text("⚠️ User not found. Please use /start first.")
        await callback.answer()
        return

    is_admin = user_id in ADMIN_IDS

    if not is_admin and user["balance"] < ORDER_COST:
        await callback.message.edit_text("❌ Insufficient balance!")
        await callback.answer()
        return

    try:
        await callback.answer("Order confirmed. Processing...")
    except Exception:
        pass

    await callback.message.edit_text(
        "⏳ *Processing your order...*\n\n"
        "Please wait while we generate your Google One partner link.",
        parse_mode="Markdown",
    )

    order_id = await create_order(user_id, data["gmail"])

    if not is_admin:
        deducted = await deduct_balance(user_id, ORDER_COST, "order", f"Order #{order_id}")
        if not deducted:
            await update_order(order_id, "failed", failure_reason="BALANCE_DEDUCT_FAILED")
            await callback.message.edit_text("❌ Balance deduction failed. Please try again.")
            return

    proxy_url = await get_random_user_proxy(user_id)
    login_fn = functools.partial(
        google_login_and_get_link,
        data["gmail"],
        data["password"],
        data.get("totp_secret"),
        backup_code=data.get("backup_code"),
        proxy_url=proxy_url,
    )
    try:
        result = await asyncio.to_thread(login_fn)
    except Exception as exc:
        logger.exception("Order #%s crashed during Google login for user %s", order_id, user_id)
        await update_order(order_id, "failed", failure_reason="INTERNAL_ERROR")
        if not is_admin:
            await add_balance(user_id, ORDER_COST, "refund", f"Refund for crashed Order #{order_id}")

        refund_line = (
            f"💰 Your balance has been *refunded* (`{ORDER_COST}` credits).\n\n"
            if not is_admin
            else "👑 Admin order — no balance was charged.\n\n"
        )
        await callback.message.answer(
            "❌ *Order Failed*\n\n"
            "An internal error occurred while processing your order.\n\n"
            f"{refund_line}"
            "Please try again or contact support.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ *Order Crashed*\n\n"
                    f"User: {escape_md(callback.from_user.full_name)} (`{user_id}`)\n"
                    f"Gmail: `{escape_md(data['gmail'])}`\n"
                    f"Order #{order_id}\n"
                    f"Error: `{escape_md(type(exc).__name__)}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        return

    if result["success"]:
        link = result["link"]
        await update_order(order_id, "success", link)

        success_msg = (
            f"✅ *Done!*\n"
            f"Here is your Google Ai Pro 12-Month Trial link:\n"
            f"`{escape_md(link)}`\n\n"
            f"⚠️ *Be Careful!* Copy this link and paste this into a browser where "
            f"*only this gmail account is logged in.* Sign out all other accounts "
            f"other than this one or you'll face this *\"Can't redeem offer. The offer "
            f"has already been used\"* Problem!"
        )
        await callback.message.answer(success_msg, parse_mode="Markdown", reply_markup=main_menu())

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📦 *Order Update from Admin:*\n\n"
                    f"User: {escape_md(callback.from_user.full_name)} (`{user_id}`)\n"
                    f"Gmail: `{escape_md(data['gmail'])}`\n"
                    f"Order #{order_id} — ✅ Success\n"
                    f"Charged: `{ORDER_COST}` credits",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    else:
        reason_code = result.get("reason") or "UNKNOWN"
        await update_order(order_id, "failed", failure_reason=reason_code)
        if not is_admin:
            await add_balance(user_id, ORDER_COST, "refund", f"Refund for failed Order #{order_id}")

        refund_line = (
            f"💰 Your balance has been *refunded* (`{ORDER_COST}` credits).\n\n"
            if not is_admin
            else "👑 Admin order — no balance was charged.\n\n"
        )

        proxy_hint = await _maybe_proxy_hint(user_id, reason_code)

        error_msg = (
            f"❌ *Order Failed*\n\n"
            f"Reason: `{escape_md(result['error'])}`\n\n"
            f"{refund_line}"
            f"{proxy_hint}"
            f"Please check your credentials and try again."
        )
        await callback.message.answer(error_msg, parse_mode="Markdown", reply_markup=main_menu())

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📦 *Order Failed:*\n\n"
                    f"User: {escape_md(callback.from_user.full_name)} (`{user_id}`)\n"
                    f"Gmail: `{escape_md(data['gmail'])}`\n"
                    f"Order #{order_id} — ❌ Failed\n"
                    f"Reason: `{escape_md(result['error'])}`\n"
                    f"Code: `{reason_code}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
