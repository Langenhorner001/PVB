import time
import platform
import sys
from datetime import datetime

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from db import get_stats, get_user
from config import ADMIN_IDS, BOT_NAME, ORDER_COST, REFERRAL_REWARD, SUPPORT_USERNAME

router = Router()

BOT_STARTED_AT = time.time()


def _format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


@router.message(Command("help", "start_help", prefix="/."))
async def cmd_help(message: Message):
    is_admin = message.from_user.id in ADMIN_IDS

    text = (
        "╔═══════════════════════════════╗\n"
        f"   ⚡️ *{BOT_NAME}* ⚡️\n"
        "╚═══════════════════════════════╝\n\n"
        "🌟 *Yahan aap ki har command ka jawab hai!*\n"
        "_Tip: Har command `/` ya `.` se chal jati hai._\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 *USER COMMANDS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 `/start` — Bot start karein\n"
        "🛒 `/help` — Yeh menu dobara dekhein\n"
        "💰 *Balance* — Apna balance check karein\n"
        "💳 `/topup` — Balance recharge karein\n"
        "🛍 *Place Order* — Naya order place karein\n"
        "📋 `/history` — Apne purane orders\n"
        "🧾 `/mytopups` — Top-up history\n"
        "🎁 *Refer & Earn* — Dost laao, credits paao\n"
        "📖 `/guide` — Bot kaise use karein\n"
        "📞 `/contact` — Support se rabta\n"
        "❌ `/cancel` — Chal raha order/topup cancel\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛰 *UTILITY COMMANDS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏓 `/ping` — Bot ki speed check karein\n"
        "📊 `/stats` — Bot ke total stats\n"
        "🟢 `/status` — Bot online hai ya nahi\n"
        "👑 `/sudo_users` — Admins ki list\n"
    )

    if is_admin:
        text += (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👑 *ADMIN COMMANDS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔐 `/admin` — Admin panel kholein\n"
            "📢 `/broadcast` — Sab users ko message\n"
            "💳 `/pendingtopups` — Pending top-up requests\n"
            "👑 *Note:* Aap ke orders muft hain — koi credit nahi katega!\n"
        )

    text += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Order Cost:* `{ORDER_COST}` credits\n"
        f"🎁 *Referral Reward:* `{REFERRAL_REWARD}` credits\n"
        f"📞 *Support:* {SUPPORT_USERNAME}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 _Powered by Pixel Verification_ 💎"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("ping", prefix="/."))
async def cmd_ping(message: Message, bot: Bot):
    sent_at = time.time()
    sent_msg = await message.answer("🏓 Pinging...")
    rtt_ms = int((time.time() - sent_at) * 1000)

    me = await bot.get_me()
    text = (
        "🏓 *Pong!*\n\n"
        f"⚡️ Latency: `{rtt_ms} ms`\n"
        f"🤖 Bot: @{me.username}\n"
        f"🟢 Status: *Online*"
    )
    await sent_msg.edit_text(text, parse_mode="Markdown")


@router.message(Command("stats", prefix="/."))
async def cmd_stats(message: Message):
    stats = await get_stats()
    user = await get_user(message.from_user.id)
    my_balance = user["balance"] if user else 0

    text = (
        "📊 *Bot Statistics*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: `{stats['total_users']}`\n"
        f"📦 Total Orders: `{stats['total_orders']}`\n"
        f"✅ Successful Orders: `{stats['success_orders']}`\n"
        f"❌ Failed/Other: `{stats['total_orders'] - stats['success_orders']}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Aap ka Balance: `{my_balance}` credits\n"
        f"⏱ Uptime: `{_format_uptime(time.time() - BOT_STARTED_AT)}`"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("status", prefix="/."))
async def cmd_status(message: Message, bot: Bot):
    sent_at = time.time()
    me = await bot.get_me()
    rtt_ms = int((time.time() - sent_at) * 1000)
    uptime = _format_uptime(time.time() - BOT_STARTED_AT)

    text = (
        "🟢 *Bot Status: ONLINE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: @{me.username}\n"
        f"🆔 ID: `{me.id}`\n"
        f"⚡️ API Latency: `{rtt_ms} ms`\n"
        f"⏱ Uptime: `{uptime}`\n"
        f"🐍 Python: `{sys.version.split()[0]}`\n"
        f"💻 Platform: `{platform.system()} {platform.release()}`\n"
        f"📅 Server Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Sab kuch theek chal raha hai!"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("sudo_users", "sudo", "admins", prefix="/."))
async def cmd_sudo_users(message: Message, bot: Bot):
    if not ADMIN_IDS:
        await message.answer("⚠️ Koi admin configure nahi hai.")
        return

    lines = ["👑 *Sudo Users (Admins)*", "━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for idx, admin_id in enumerate(ADMIN_IDS, start=1):
        try:
            chat = await bot.get_chat(admin_id)
            name = chat.full_name or "Unknown"
            uname = f"@{chat.username}" if chat.username else "—"
            lines.append(f"{idx}. *{name}* ({uname}) — `{admin_id}`")
        except Exception:
            lines.append(f"{idx}. _Unknown_ — `{admin_id}`")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Total Admins: `{len(ADMIN_IDS)}`")

    await message.answer("\n".join(lines), parse_mode="Markdown")
