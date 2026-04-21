import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from db import get_user, deduct_balance, add_balance, create_order, update_order
from keyboards import main_menu, cancel_kb, confirm_order_kb
from google_auth import google_login_and_get_link
from config import ORDER_COST, ADMIN_IDS
from aiogram import Bot

router = Router()


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

    if user["balance"] < ORDER_COST:
        await message.answer(
            f"❌ *Insufficient Balance!*\n\n"
            f"💰 Your balance: `{user['balance']}` credits\n"
            f"💵 Order cost: `{ORDER_COST}` credits\n\n"
            f"Please top-up your balance to continue.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
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


@router.message(Command("cancel"))
async def cancel_order(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ Order cancelled.", reply_markup=main_menu())
    else:
        await message.answer("Nothing to cancel.", reply_markup=main_menu())


@router.message(OrderState.waiting_gmail)
async def got_gmail(message: Message, state: FSMContext):
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("⚠️ Invalid email. Please enter a valid Gmail address:")
        return
    await state.update_data(gmail=email)
    await state.set_state(OrderState.waiting_password)
    await message.answer(
        f"✅ Gmail: `{email}`\n\n"
        f"🔒 *Step 2 of 3* — Enter your *Google account password*:\n\n"
        f"_(Type /cancel to stop)_",
        parse_mode="Markdown",
    )


@router.message(OrderState.waiting_password)
async def got_password(message: Message, state: FSMContext):
    password = message.text.strip()
    if len(password) < 6:
        await message.answer("⚠️ Password too short. Please enter your correct password:")
        return
    await state.update_data(password=password)
    await state.set_state(OrderState.waiting_2fa)
    await message.answer(
        f"🔐 *Step 3 of 3* — Enter your *2FA Secret Key* (TOTP):\n\n"
        f"This is the secret key from your authenticator app setup\n"
        f"(e.g., `JBSWY3DPEHPK3PXP`)\n\n"
        f"_(Type /cancel to stop)_",
        parse_mode="Markdown",
    )


@router.message(OrderState.waiting_2fa)
async def got_2fa(message: Message, state: FSMContext):
    secret = message.text.strip().replace(" ", "")
    if len(secret) < 8:
        await message.answer("⚠️ 2FA secret seems too short. Please check and re-enter:")
        return

    await state.update_data(totp_secret=secret)
    data = await state.get_data()
    await state.set_state(OrderState.confirming)

    await message.answer(
        f"📋 *Order Summary*\n\n"
        f"📧 Gmail: `{data['gmail']}`\n"
        f"🔑 Password: `{'*' * len(data['password'])}`\n"
        f"🔐 2FA Secret: `{secret[:4]}...`\n\n"
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

    if user["balance"] < ORDER_COST:
        await callback.message.edit_text("❌ Insufficient balance!")
        await callback.answer()
        return

    await callback.message.edit_text(
        "⏳ *Processing your order...*\n\n"
        "Please wait while we generate your Google One partner link.",
        parse_mode="Markdown",
    )

    order_id = await create_order(user_id, data["gmail"])
    deducted = await deduct_balance(user_id, ORDER_COST, "order", f"Order #{order_id}")

    if not deducted:
        await callback.message.edit_text("❌ Balance deduction failed. Please try again.")
        await callback.answer()
        return

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        google_login_and_get_link,
        data["gmail"],
        data["password"],
        data["totp_secret"],
    )

    if result["success"]:
        link = result["link"]
        await update_order(order_id, "success", link)

        success_msg = (
            f"✅ *Done!*\n"
            f"Here is your Google Ai Pro 12-Month Trial link:\n"
            f"{link}\n\n"
            f"⚠️ *Be Careful!* Copy this link and paste this into a browser where "
            f"*only this gmail account is logged in.* Sign out all other accounts "
            f"other than this one or you'll face this *\"Can't redeem offer. The offer "
            f"has already been used\"* Problem!"
        )
        await callback.message.answer(success_msg, parse_mode="Markdown", reply_markup=main_menu())

        user_obj = await get_user(user_id)
        updated_balance = user_obj["balance"] if user_obj else 0

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📦 *Order Update from Admin:*\n\n"
                    f"User: {callback.from_user.full_name} (`{user_id}`)\n"
                    f"Gmail: `{data['gmail']}`\n"
                    f"Order #{order_id} — ✅ Success\n"
                    f"tap {ORDER_COST}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    else:
        await update_order(order_id, "failed")
        await add_balance(user_id, ORDER_COST, "refund", f"Refund for failed Order #{order_id}")

        error_msg = (
            f"❌ *Order Failed*\n\n"
            f"Reason: {result['error']}\n\n"
            f"💰 Your balance has been *refunded* (`{ORDER_COST}` credits).\n\n"
            f"Please check your credentials and try again."
        )
        await callback.message.answer(error_msg, parse_mode="Markdown", reply_markup=main_menu())

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📦 *Order Failed:*\n\n"
                    f"User: {callback.from_user.full_name} (`{user_id}`)\n"
                    f"Gmail: `{data['gmail']}`\n"
                    f"Order #{order_id} — ❌ Failed\n"
                    f"Reason: {result['error']}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    await callback.answer()
