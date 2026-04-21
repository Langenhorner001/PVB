import json
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from db import (
    create_topup_request,
    get_topup_request,
    claim_topup_request,
    get_pending_topups,
    get_user_topups,
    add_balance,
    get_user,
    record_payment,
)
from helpers import escape_md
from keyboards import (
    main_menu,
    cancel_kb,
    topup_method_choice_kb,
    topup_amounts_kb,
    topup_method_kb,
    topup_admin_kb,
    topup_packages_kb,
)
from config import (
    TOPUP_AMOUNTS,
    TOPUP_PACKAGES,
    MIN_TOPUP,
    PAYMENT_EASYPAISA,
    PAYMENT_JAZZCASH,
    PAYMENT_ACCOUNT_NAME,
    ADMIN_IDS,
    SUPPORT_USERNAME,
    ORDER_COST,
)

logger = logging.getLogger(__name__)
router = Router()

_PACKAGES_BY_ID = {pkg["id"]: pkg for pkg in TOPUP_PACKAGES}

METHOD_LABELS = {"easypaisa": "Easypaisa", "jazzcash": "JazzCash"}


class TopUpFlow(StatesGroup):
    waiting_custom_amount = State()
    waiting_method = State()
    waiting_transaction_ref = State()


# ─────────────────────────── Entry points ────────────────────────────

@router.message(Command("topup", prefix="/."))
@router.message(F.text == "💳 Top-Up")
async def cmd_topup(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return
    await message.answer(
        "💳 *Top-Up Balance*\n\n"
        "Choose your preferred payment method:",
        parse_mode="Markdown",
        reply_markup=topup_method_choice_kb(),
    )


@router.callback_query(F.data == "open_topup")
async def cb_open_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "💳 *Top-Up Balance*\n\n"
        "Choose your preferred payment method:",
        parse_mode="Markdown",
        reply_markup=topup_method_choice_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "topup_cancel")
async def cb_topup_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Top-Up cancelled.")
    await callback.message.answer("Back to menu:", reply_markup=main_menu())
    await callback.answer()


# ─────────────────────── Telegram Stars flow ─────────────────────────

@router.callback_query(F.data == "open_stars_topup")
async def cb_open_stars_topup(callback: CallbackQuery):
    lines = ["⭐ *Top-Up via Telegram Stars*\n", "Select a package:\n"]
    for pkg in TOPUP_PACKAGES:
        lines.append(f"{pkg['emoji']} *{pkg['label']}* — {pkg['stars']} ⭐ Telegram Stars")
    lines.append("\n_Payment is processed instantly and securely via Telegram Stars._")
    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=topup_packages_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pkg_"))
async def cb_stars_select_package(callback: CallbackQuery, bot: Bot):
    pkg = _PACKAGES_BY_ID.get(callback.data)
    if not pkg:
        await callback.answer("Unknown package.", show_alert=True)
        return

    await callback.answer()

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{pkg['emoji']} {pkg['label']}",
        description=(
            f"Add {pkg['credits']} credits to your balance.\n"
            f"Each order costs {ORDER_COST} credits."
        ),
        payload=json.dumps({"pkg_id": pkg["id"], "credits": pkg["credits"], "stars": pkg["stars"]}),
        currency="XTR",
        prices=[LabeledPrice(label=pkg["label"], amount=pkg["stars"])],
    )

    await callback.message.edit_text(
        f"✅ Invoice sent for *{pkg['label']}* ({pkg['stars']} ⭐).\n\n"
        f"Complete the payment in the message above.",
        parse_mode="Markdown",
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot):
    payment = message.successful_payment
    user_id = message.from_user.id

    try:
        payload = json.loads(payment.invoice_payload)
    except (json.JSONDecodeError, KeyError):
        logger.error("top-up stars: invalid payload for user %s: %s", user_id, payment.invoice_payload)
        await message.answer("⚠️ Payment received but payload was invalid. Please contact support.")
        return

    pkg_id = payload.get("pkg_id")
    credits = payload.get("credits")
    expected_stars = payload.get("stars")

    pkg = _PACKAGES_BY_ID.get(pkg_id)
    if not pkg or credits is None:
        logger.error("top-up stars: unknown package '%s' for user %s", pkg_id, user_id)
        await message.answer("⚠️ Payment received but package was unrecognised. Please contact support.")
        return

    if payment.currency != "XTR" or payment.total_amount != expected_stars:
        logger.error(
            "top-up stars: payment mismatch for user %s — expected %s XTR, got %s %s",
            user_id, expected_stars, payment.total_amount, payment.currency,
        )
        await message.answer("⚠️ Payment amount mismatch. Please contact support.")
        return

    charge_id = payment.telegram_payment_charge_id or ""
    is_new = await record_payment(charge_id, user_id, credits)
    if not is_new:
        logger.warning("top-up stars: duplicate charge_id %s for user %s — ignored", charge_id, user_id)
        return

    await add_balance(user_id, credits, "topup", f"Top-Up (Stars): {pkg['label']}")

    user = await get_user(user_id)
    new_balance = user["balance"] if user else credits

    await message.answer(
        f"✅ *Payment Successful!*\n\n"
        f"💰 *{credits} credits* have been added to your balance.\n"
        f"🏦 New Balance: `{new_balance}` credits\n\n"
        f"You can now place orders. Each order costs {ORDER_COST} credits.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💳 *Top-Up Received (Stars)*\n\n"
                f"User: {message.from_user.full_name} (`{user_id}`)\n"
                f"Package: {pkg['label']}\n"
                f"Credits Added: `{credits}`\n"
                f"Stars Paid: `{expected_stars}` ⭐\n"
                f"New Balance: `{new_balance}` credits",
                parse_mode="Markdown",
            )
        except Exception:
            logger.warning("top-up stars: failed to notify admin %s for user %s top-up", admin_id, user_id)


# ──────────────────── Easypaisa / JazzCash manual flow ───────────────

@router.callback_query(F.data == "open_manual_topup")
async def cb_open_manual_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "📱 *Top-Up via Easypaisa / JazzCash*\n\n"
        "Amount select karein ya custom amount likhein.\n\n"
        f"_Minimum top-up: {MIN_TOPUP} credits_"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=topup_amounts_kb(TOPUP_AMOUNTS))
    await callback.answer()


@router.callback_query(F.data.startswith("topup_amt:"))
async def cb_topup_amount(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]

    if value == "custom":
        await state.set_state(TopUpFlow.waiting_custom_amount)
        await callback.message.edit_text(
            f"✏️ *Custom Amount*\n\n"
            f"Apna desired amount (credits) likhein.\n"
            f"_Minimum: {MIN_TOPUP}_",
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    try:
        amount = int(value)
    except ValueError:
        await callback.answer("Ghalat amount.", show_alert=True)
        return

    if amount not in TOPUP_AMOUNTS or amount < MIN_TOPUP:
        await callback.answer("Ghalat amount.", show_alert=True)
        return

    await _ask_method(callback.message, state, amount, edit=True)
    await callback.answer()


@router.message(TopUpFlow.waiting_custom_amount)
async def msg_custom_amount(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(f"⚠️ Sirf number likhein. Minimum {MIN_TOPUP}.")
        return
    amount = int(text)
    if amount < MIN_TOPUP:
        await message.answer(f"⚠️ Amount {MIN_TOPUP} se kam nahi ho sakta.")
        return
    await _ask_method(message, state, amount, edit=False)


async def _ask_method(message: Message, state: FSMContext, amount: int, edit: bool):
    await state.set_state(TopUpFlow.waiting_method)
    await state.update_data(amount=amount)
    text = (
        f"💳 *Top-Up: {amount} credits*\n\n"
        "Payment method select karein:"
    )
    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=topup_method_kb())
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=topup_method_kb())


@router.callback_query(TopUpFlow.waiting_method, F.data.startswith("topup_method:"))
async def cb_topup_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":", 1)[1]
    if method not in METHOD_LABELS:
        await callback.answer("Ghalat method.", show_alert=True)
        return

    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await state.clear()
        await callback.message.edit_text("⚠️ Session expired. /topup dobara chalu karein.")
        await callback.answer()
        return

    await state.update_data(method=method)
    await state.set_state(TopUpFlow.waiting_transaction_ref)

    account_number = PAYMENT_EASYPAISA if method == "easypaisa" else PAYMENT_JAZZCASH

    instructions = (
        f"💳 *Payment Instructions*\n\n"
        f"Method: *{METHOD_LABELS[method]}*\n"
        f"Amount: *{amount} PKR*\n"
        f"Account Number: `{account_number}`\n"
        f"Account Name: *{PAYMENT_ACCOUNT_NAME}*\n\n"
        f"📌 *Steps:*\n"
        f"1. Upar diye gaye number par {amount} PKR send karein.\n"
        f"2. Payment ke baad apna *Transaction ID / TRX ID* yahan paste karein.\n"
        f"3. Admin verify karke aap ka balance add kar dega (usually 5-30 minutes).\n\n"
        f"⚠️ Bina payment ke fake TRX ID submit karne par account permanently ban ho jayega.\n\n"
        f"📝 Ab *Transaction ID* likh kar bhejein:"
    )
    await callback.message.edit_text(instructions, parse_mode="Markdown")
    await callback.message.answer("Transaction ID likhein:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(TopUpFlow.waiting_transaction_ref, Command("cancel", prefix="/."))
async def cancel_topup(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Top-up cancel kar diya gaya.", reply_markup=main_menu())


@router.message(TopUpFlow.waiting_transaction_ref)
async def msg_trx_ref(message: Message, state: FSMContext, bot: Bot):
    trx = (message.text or "").strip()
    if len(trx) < 4 or len(trx) > 64:
        await message.answer("⚠️ Transaction ID 4 se 64 characters ka hona chahiye. Dobara likhein.")
        return

    data = await state.get_data()
    amount = data.get("amount")
    method = data.get("method")
    await state.clear()

    if not amount or not method:
        await message.answer("⚠️ Session expired. /topup dobara chalu karein.", reply_markup=main_menu())
        return

    user_id = message.from_user.id
    request_id = await create_topup_request(user_id, amount, method, trx)

    await message.answer(
        f"✅ *Top-Up Request Submitted*\n\n"
        f"Request ID: `#{request_id}`\n"
        f"Amount: *{amount} credits*\n"
        f"Method: *{METHOD_LABELS[method]}*\n"
        f"TRX ID: `{trx}`\n\n"
        f"Admin verify karke jald aap ko notify karega.\n"
        f"Koi issue ho to: {SUPPORT_USERNAME}",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    admin_text = (
        f"💳 *New Top-Up Request* `#{request_id}`\n\n"
        f"User: {message.from_user.full_name} (`{user_id}`)\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"Amount: *{amount} credits*\n"
        f"Method: *{METHOD_LABELS[method]}*\n"
        f"TRX ID: `{trx}`"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                parse_mode="Markdown",
                reply_markup=topup_admin_kb(request_id),
            )
        except Exception:
            logger.warning("top-up manual: failed to notify admin %s for request #%s", admin_id, request_id)


# ────────────────────── Admin approval / rejection ───────────────────

@router.callback_query(F.data.startswith("topup_approve:"))
async def cb_topup_approve(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Sirf admins ke liye.", show_alert=True)
        return

    try:
        request_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ghalat request ID.", show_alert=True)
        return

    req = await get_topup_request(request_id)
    if not req:
        await callback.answer("Request nahi mili.", show_alert=True)
        return
    if req["status"] != "pending":
        await callback.answer(f"Pehle se {req['status']}.", show_alert=True)
        return

    claimed = await claim_topup_request(
        request_id, "approved", f"Approved by {callback.from_user.id}"
    )
    if not claimed:
        await callback.answer("Yeh request pehle hi process ho chuki hai.", show_alert=True)
        return

    await add_balance(req["user_id"], req["amount"], "topup", f"Top-Up #{request_id} approved")

    user = await get_user(req["user_id"])
    new_balance = user["balance"] if user else req["amount"]

    try:
        await bot.send_message(
            req["user_id"],
            f"✅ *Top-Up Approved!*\n\n"
            f"Request `#{request_id}` approved.\n"
            f"💰 Added: *{req['amount']} credits*\n"
            f"💳 New Balance: *{new_balance} credits*\n\n"
            f"Shukriya! Ab aap order place kar sakte hain.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    except Exception:
        pass

    safe_admin = escape_md(callback.from_user.full_name)
    original = callback.message.text or ""
    await callback.message.edit_text(
        f"{escape_md(original)}\n\n✅ *APPROVED* by {safe_admin}",
        parse_mode="Markdown",
    )
    await callback.answer("Approved & balance added.")


@router.callback_query(F.data.startswith("topup_reject:"))
async def cb_topup_reject(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Sirf admins ke liye.", show_alert=True)
        return

    try:
        request_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ghalat request ID.", show_alert=True)
        return

    req = await get_topup_request(request_id)
    if not req:
        await callback.answer("Request nahi mili.", show_alert=True)
        return
    if req["status"] != "pending":
        await callback.answer(f"Pehle se {req['status']}.", show_alert=True)
        return

    claimed = await claim_topup_request(
        request_id, "rejected", f"Rejected by {callback.from_user.id}"
    )
    if not claimed:
        await callback.answer("Yeh request pehle hi process ho chuki hai.", show_alert=True)
        return

    try:
        await bot.send_message(
            req["user_id"],
            f"❌ *Top-Up Rejected*\n\n"
            f"Request `#{request_id}` reject ho gaya.\n"
            f"Amount: *{req['amount']} credits*\n"
            f"TRX ID: `{req['transaction_ref']}`\n\n"
            f"Agar aap ne payment ki hai aur yeh galti se reject hua hai, "
            f"to support se contact karein: {SUPPORT_USERNAME}",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    except Exception:
        pass

    safe_admin = escape_md(callback.from_user.full_name)
    original = callback.message.text or ""
    await callback.message.edit_text(
        f"{escape_md(original)}\n\n❌ *REJECTED* by {safe_admin}",
        parse_mode="Markdown",
    )
    await callback.answer("Rejected.")


# ─────────────────────── User history commands ───────────────────────

@router.message(Command("mytopups", prefix="/."))
async def cmd_my_topups(message: Message):
    rows = await get_user_topups(message.from_user.id)
    if not rows:
        await message.answer("📭 Abhi tak koi top-up request nahi hai.\n/topup se nayi request banayein.")
        return

    lines = ["💳 *Aap ki Top-Up History:*\n"]
    icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    for r in rows:
        icon = icons.get(r["status"], "•")
        lines.append(
            f"{icon} `#{r['id']}` — *{r['amount']}* credits — "
            f"{METHOD_LABELS.get(r['payment_method'], r['payment_method'])} — "
            f"_{r['status']}_"
        )
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("pendingtopups", prefix="/."))
async def cmd_pending_topups(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    rows = await get_pending_topups()
    if not rows:
        await message.answer("✅ Koi pending top-up request nahi hai.")
        return

    for r in rows:
        text = (
            f"💳 *Pending Top-Up* `#{r['id']}`\n"
            f"User: `{r['user_id']}`\n"
            f"Amount: *{r['amount']} credits*\n"
            f"Method: *{METHOD_LABELS.get(r['payment_method'], r['payment_method'])}*\n"
            f"TRX ID: `{r['transaction_ref']}`\n"
            f"Created: {r['created_at']}"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=topup_admin_kb(r["id"]))
