import asyncio
import csv
import io
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest
from db import (
    get_stats, get_all_users, add_balance, deduct_balance, ban_user, get_user,
    get_recent_orders, search_orders, get_order_by_id, update_order, refund_order,
    get_topup_revenue_stats, get_topup_transactions_for_export,
)
from keyboards import admin_menu, main_menu, admin_orders_list_kb, admin_order_kb, admin_revenue_kb
from helpers import escape_md
from config import ADMIN_IDS, ORDER_COST

logger = logging.getLogger(__name__)
MAX_ADMIN_CREDIT = 1_000_000
BROADCAST_DELAY = 0.05  # ~20 msgs/sec, well under Telegram's 30/sec global limit

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminState(StatesGroup):
    broadcast_msg = State()
    add_bal_id = State()
    add_bal_amount = State()
    deduct_bal_id = State()
    deduct_bal_amount = State()
    ban_id = State()
    unban_id = State()
    order_search_query = State()
    order_success_link = State()


@router.message(Command("admin", prefix="/."))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    await message.answer("🔐 *Admin Panel*\n\nChoose an action:", parse_mode="Markdown", reply_markup=admin_menu())


@router.message(Command("broadcast", prefix="/."))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    await state.set_state(AdminState.broadcast_msg)
    await message.answer("📢 Enter the message to broadcast to all users:\n_(Type /cancel to stop)_", parse_mode="Markdown")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    stats = await get_stats()
    rev = await get_topup_revenue_stats(top_spenders_limit=0)
    await callback.message.answer(
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: `{stats['total_users']}`\n"
        f"📦 Total Orders: `{stats['total_orders']}`\n"
        f"✅ Successful Orders: `{stats['success_orders']}`\n\n"
        f"💰 *Top-Up Revenue*\n"
        f"⭐ Stars: `{rev['stars']['count']}` top-ups · "
        f"`{rev['stars']['credits']}` cr · `{rev['stars']['stars']}` ⭐\n"
        f"📱 Manual: `{rev['manual']['count']}` top-ups · "
        f"`{rev['manual']['credits']}` cr\n"
        f"📈 Total credits sold: `{rev['total_credits']}`\n\n"
        f"_Tap 💰 Top-Up Revenue for the full breakdown & CSV export._",
        parse_mode="Markdown",
    )
    await callback.answer()


def _format_revenue_text(rev: dict) -> str:
    stars = rev["stars"]
    manual = rev["manual"]
    lines = [
        "💰 *Top-Up Revenue*",
        "",
        f"⭐ Stars Top-Ups: `{stars['count']}` "
        f"→ `{stars['credits']}` credits, `{stars['stars']}` ⭐",
        f"📱 Manual Top-Ups: `{manual['count']}` → `{manual['credits']}` credits",
        f"📊 Total: `{rev['total_count']}` top-ups, "
        f"`{rev['total_credits']}` credits sold",
        "",
        "*By Stars Package:*",
    ]
    for p in rev["by_package"]:
        lines.append(
            f"• {escape_md(p['label'])} "
            f"({p['credits_per_pkg']}cr / {p['stars_per_pkg']}⭐): "
            f"`{p['count']}` sold → `{p['credits']}` cr, `{p['stars']}` ⭐"
        )
    if rev["top_spenders"]:
        lines.append("")
        lines.append("*Top Spenders:*")
        for i, s in enumerate(rev["top_spenders"], 1):
            name = s.get("full_name") or s.get("username") or "Unknown"
            lines.append(
                f"{i}. {escape_md(name)} (`{s['user_id']}`) — `{s['credits']}` cr"
            )
    return "\n".join(lines)


@router.callback_query(F.data == "admin_revenue")
async def admin_revenue(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    rev = await get_topup_revenue_stats()
    await callback.message.answer(
        _format_revenue_text(rev),
        parse_mode="Markdown",
        reply_markup=admin_revenue_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_revenue_export")
async def admin_revenue_export(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.answer("Generating export…")
    rows = await get_topup_transactions_for_export()
    rev = await get_topup_revenue_stats()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "transaction_id", "user_id", "username", "full_name",
        "credits", "description", "created_at",
    ])
    for r in rows:
        writer.writerow([
            r.get("id"),
            r.get("user_id"),
            r.get("username") or "",
            r.get("full_name") or "",
            r.get("amount"),
            r.get("description") or "",
            r.get("created_at") or "",
        ])
    writer.writerow([])
    writer.writerow(["# Summary"])
    writer.writerow(["stars_topups_count", rev["stars"]["count"]])
    writer.writerow(["stars_credits_sold", rev["stars"]["credits"]])
    writer.writerow(["stars_total_stars", rev["stars"]["stars"]])
    writer.writerow(["manual_topups_count", rev["manual"]["count"]])
    writer.writerow(["manual_credits_sold", rev["manual"]["credits"]])
    writer.writerow(["total_credits_sold", rev["total_credits"]])
    writer.writerow([])
    writer.writerow(["# Per-Package Breakdown"])
    writer.writerow(["package", "credits_per_pkg", "stars_per_pkg", "count", "credits", "stars"])
    for p in rev["by_package"]:
        writer.writerow([
            p["label"], p["credits_per_pkg"], p["stars_per_pkg"],
            p["count"], p["credits"], p["stars"],
        ])

    data = buf.getvalue().encode("utf-8")
    fname = f"topup_revenue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    await callback.message.answer_document(
        BufferedInputFile(data, filename=fname),
        caption=f"📥 Top-up revenue export ({len(rows)} transactions)",
    )


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.broadcast_msg)
    await callback.message.answer("📢 Enter the message to broadcast to all users:\n_(Type /cancel to stop)_", parse_mode="Markdown")
    await callback.answer()


@router.message(AdminState.broadcast_msg)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not message.text:
        await message.answer("⚠️ Broadcast must be a text message.", reply_markup=main_menu())
        return
    users = await get_all_users()
    body = message.text
    sent = 0
    failed = 0
    blocked = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 *Admin Message:*\n\n{body}", parse_mode="Markdown")
            sent += 1
        except TelegramRetryAfter as e:
            logger.warning("Broadcast flood-wait %ss for %s", e.retry_after, uid)
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.send_message(uid, f"📢 *Admin Message:*\n\n{body}", parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1
        except TelegramForbiddenError:
            blocked += 1
        except (TelegramBadRequest, Exception) as e:
            logger.warning("Broadcast failed for %s: %s", uid, e)
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY)
    await message.answer(
        f"✅ Broadcast complete!\n"
        f"✅ Sent: {sent}\n"
        f"🚫 Blocked bot: {blocked}\n"
        f"❌ Failed: {failed}",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "admin_add_bal")
async def admin_add_bal_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.add_bal_id)
    await callback.message.answer("Enter the *User ID* to add balance to:\n_(Type /cancel to stop)_", parse_mode="Markdown")
    await callback.answer()


@router.message(AdminState.add_bal_id)
async def admin_add_bal_id(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    await state.update_data(target_id=int(message.text.strip()))
    await state.set_state(AdminState.add_bal_amount)
    await message.answer("Enter the *amount* of credits to add:")


@router.message(AdminState.add_bal_amount)
async def admin_add_bal_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Please enter a valid number:")
        return
    amount = int(message.text.strip())
    if amount <= 0 or amount > MAX_ADMIN_CREDIT:
        await message.answer(f"⚠️ Amount must be between 1 and {MAX_ADMIN_CREDIT}.")
        return
    data = await state.get_data()
    await state.clear()
    await add_balance(data["target_id"], amount, "admin_credit", f"Admin added {amount} credits")
    user = await get_user(data["target_id"])
    new_bal = user["balance"] if user else "N/A"
    await message.answer(
        f"✅ Added `{amount}` credits to user `{data['target_id']}`.\n"
        f"New balance: `{new_bal}`",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "admin_deduct_bal")
async def admin_deduct_bal_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.deduct_bal_id)
    await callback.message.answer("Enter the *User ID* to deduct balance from:", parse_mode="Markdown")
    await callback.answer()


@router.message(AdminState.deduct_bal_id)
async def admin_deduct_bal_id(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    await state.update_data(target_id=int(message.text.strip()))
    await state.set_state(AdminState.deduct_bal_amount)
    await message.answer("Enter the *amount* to deduct:", parse_mode="Markdown")


@router.message(AdminState.deduct_bal_amount)
async def admin_deduct_bal_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Please enter a valid number:")
        return
    amount = int(message.text.strip())
    if amount <= 0 or amount > MAX_ADMIN_CREDIT:
        await message.answer(f"⚠️ Amount must be between 1 and {MAX_ADMIN_CREDIT}.")
        return
    data = await state.get_data()
    await state.clear()
    success = await deduct_balance(data["target_id"], amount, "admin_deduct", f"Admin deducted {amount} credits")
    if success:
        user = await get_user(data["target_id"])
        new_bal = user["balance"] if user else "N/A"
        await message.answer(
            f"✅ Deducted `{amount}` credits from user `{data['target_id']}`.\nNew balance: `{new_bal}`",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    else:
        await message.answer("❌ Failed — user not found or insufficient balance.", reply_markup=main_menu())


@router.callback_query(F.data == "admin_ban")
async def admin_ban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.ban_id)
    await callback.message.answer("Enter the *User ID* to ban:", parse_mode="Markdown")
    await callback.answer()


@router.message(AdminState.ban_id)
async def admin_do_ban(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    uid = int(message.text.strip())
    await state.clear()
    await ban_user(uid, True)
    await message.answer(f"🚫 User `{uid}` has been banned.", parse_mode="Markdown", reply_markup=main_menu())


@router.callback_query(F.data == "admin_unban")
async def admin_unban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.unban_id)
    await callback.message.answer("Enter the *User ID* to unban:", parse_mode="Markdown")
    await callback.answer()


@router.message(AdminState.unban_id)
async def admin_do_unban(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    uid = int(message.text.strip())
    await state.clear()
    await ban_user(uid, False)
    await message.answer(f"✅ User `{uid}` has been unbanned.", parse_mode="Markdown", reply_markup=main_menu())


def _format_order_detail(order: dict) -> str:
    status_icon = {"success": "✅", "failed": "❌", "processing": "⏳", "refunded": "💸"}.get(order["status"], "❓")
    name = order.get("full_name") or order.get("username") or "Unknown"
    lines = [
        f"📦 *Order #{order['id']}*",
        f"",
        f"👤 User: {escape_md(name)} (`{order['user_id']}`)",
        f"📧 Gmail: `{escape_md(order['gmail'])}`",
        f"📌 Status: {status_icon} `{order['status']}`",
        f"🕐 Created: `{order['created_at'][:16]}`",
    ]
    if order.get("generated_link"):
        lines.append(f"🔗 Link: `{escape_md(order['generated_link'])}`")
    return "\n".join(lines)


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await callback.message.answer("🔐 *Admin Panel*\n\nChoose an action:", parse_mode="Markdown", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    orders = await get_recent_orders(limit=15)
    stats = await get_stats()
    header = (
        f"📦 *Recent Orders*\n\n"
        f"Total Orders: `{stats['total_orders']}` | Successful: `{stats['success_orders']}`\n\n"
        f"Showing last {len(orders)}:"
    )
    if not orders:
        header = "📦 *Orders*\n\nNo orders found."
    await callback.message.answer(header, parse_mode="Markdown", reply_markup=admin_orders_list_kb(orders))
    await callback.answer()


@router.callback_query(F.data == "admin_order_search")
async def admin_order_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    await state.set_state(AdminState.order_search_query)
    await callback.message.answer(
        "🔍 *Search Orders*\n\nEnter a *Gmail address* (or part of it), *User ID*, or *Order ID*:\n_(Type /cancel to stop)_",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminState.order_search_query)
async def admin_order_search_execute(message: Message, state: FSMContext):
    query = message.text.strip() if message.text else ""
    if not query:
        await message.answer("Please enter a search term:")
        return
    await state.clear()
    orders = await search_orders(query, limit=15)
    if not orders:
        await message.answer(
            f"🔍 No orders found for `{escape_md(query)}`.",
            parse_mode="Markdown",
            reply_markup=admin_orders_list_kb([]),
        )
        return
    await message.answer(
        f"🔍 *Search Results* for `{escape_md(query)}`\n\nFound {len(orders)} order(s):",
        parse_mode="Markdown",
        reply_markup=admin_orders_list_kb(orders),
    )


@router.callback_query(F.data.startswith("admin_order_detail:"))
async def admin_order_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid order ID.", show_alert=True)
        return
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    text = _format_order_detail(order)
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=admin_order_kb(order_id, order["status"]))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_order_success:"))
async def admin_order_success_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid order ID.", show_alert=True)
        return
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    await state.update_data(target_order_id=order_id)
    await state.set_state(AdminState.order_success_link)
    await callback.message.answer(
        f"✅ *Mark Order #{order_id} as Successful*\n\nPaste the partner link to assign:\n_(Type /cancel to stop)_",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminState.order_success_link)
async def admin_order_success_link(message: Message, state: FSMContext, bot: Bot):
    link = message.text.strip() if message.text else ""
    if not link or not link.startswith("http"):
        await message.answer("⚠️ Please enter a valid URL (starting with http):")
        return
    data = await state.get_data()
    order_id = data["target_order_id"]
    await state.clear()
    await update_order(order_id, "success", link)
    order = await get_order_by_id(order_id)
    await message.answer(
        f"✅ Order `#{order_id}` marked as *successful*.\n🔗 Link set.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    if order:
        try:
            await bot.send_message(
                order["user_id"],
                f"✅ *Your order has been resolved!*\n\n"
                f"Order #{order_id} has been manually marked as successful by an admin.\n\n"
                f"🔗 Your Google AI Pro link:\n{link}\n\n"
                f"⚠️ Use this link in a browser where *only this Gmail account* is logged in.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin_order_refund:"))
async def admin_order_refund(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied", show_alert=True)
        return
    try:
        order_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid order ID.", show_alert=True)
        return
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    if order["status"] == "refunded":
        await callback.answer("This order has already been refunded.", show_alert=True)
        return
    success = await refund_order(order_id, ORDER_COST)
    if not success:
        await callback.answer("Refund failed — order may already be refunded.", show_alert=True)
        return
    await callback.message.answer(
        f"💸 Order `#{order_id}` refunded.\n`{ORDER_COST}` credits returned to user `{order['user_id']}`.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    try:
        await bot.send_message(
            order["user_id"],
            f"💸 *Refund Processed*\n\n"
            f"Order #{order_id} has been refunded by an admin.\n"
            f"`{ORDER_COST}` credits have been added back to your balance.",
            parse_mode="Markdown",
        )
    except Exception:
        pass
    await callback.answer("Refund issued.")
