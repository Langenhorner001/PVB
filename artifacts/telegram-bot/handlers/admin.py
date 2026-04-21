from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from db import get_stats, get_all_users, add_balance, deduct_balance, ban_user, get_user
from keyboards import admin_menu, main_menu
from config import ADMIN_IDS

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


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Access denied.")
        return
    await message.answer("🔐 *Admin Panel*\n\nChoose an action:", parse_mode="Markdown", reply_markup=admin_menu())


@router.message(Command("broadcast"))
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
    await callback.message.answer(
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: `{stats['total_users']}`\n"
        f"📦 Total Orders: `{stats['total_orders']}`\n"
        f"✅ Successful Orders: `{stats['success_orders']}`\n",
        parse_mode="Markdown",
    )
    await callback.answer()


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
    users = await get_all_users()
    sent = 0
    failed = 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 *Admin Message:*\n\n{message.text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"✅ Broadcast complete!\n✅ Sent: {sent}\n❌ Failed: {failed}", reply_markup=main_menu())


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
    if not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    await state.update_data(target_id=int(message.text.strip()))
    await state.set_state(AdminState.add_bal_amount)
    await message.answer("Enter the *amount* of credits to add:")


@router.message(AdminState.add_bal_amount)
async def admin_add_bal_amount(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Please enter a valid number:")
        return
    data = await state.get_data()
    amount = int(message.text.strip())
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
    if not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    await state.update_data(target_id=int(message.text.strip()))
    await state.set_state(AdminState.deduct_bal_amount)
    await message.answer("Enter the *amount* to deduct:", parse_mode="Markdown")


@router.message(AdminState.deduct_bal_amount)
async def admin_deduct_bal_amount(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Please enter a valid number:")
        return
    data = await state.get_data()
    amount = int(message.text.strip())
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
    if not message.text.strip().isdigit():
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
    if not message.text.strip().isdigit():
        await message.answer("Please enter a valid numeric User ID:")
        return
    uid = int(message.text.strip())
    await state.clear()
    await ban_user(uid, False)
    await message.answer(f"✅ User `{uid}` has been unbanned.", parse_mode="Markdown", reply_markup=main_menu())
