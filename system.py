import os
import time
import platform
import sys
from datetime import datetime

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from db import get_stats, get_user, list_user_proxies
from google_auth import REASON_LABELS
from helpers import escape_md
from config import ADMIN_IDS, BOT_NAME, DB_PATH, ORDER_COST, REFERRAL_REWARD, SUPPORT_USERNAME

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
        "🆔 `/myid` — Apni Telegram ID dekhein\n"
        "👑 `/sudo_users` — Admins ki list\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 *PROXY COMMANDS* (optional)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 `/myproxy` — Apni proxy(s) dekhein\n"
        "➕ `/setproxy` `<url>` — Single proxy set karein\n"
        "📥 `/addproxy` `<url>` — Aur proxies add karein\n"
        "➖ `/removeproxy` — Proxy hatayein\n"
        "🧪 `/proxycheck` — Proxies test karein\n"
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
        f"🤖 Bot: `@{me.username}`\n"
        f"🟢 Status: *Online*"
    )
    await sent_msg.edit_text(text, parse_mode="Markdown")


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


@router.message(Command("stats", prefix="/."))
async def cmd_stats(message: Message):
    stats = await get_stats()
    user = await get_user(message.from_user.id)
    my_balance = user["balance"] if user else 0
    failed = stats["total_orders"] - stats["success_orders"] - stats["processing_orders"]

    breakdown_lines = []
    breakdown = stats.get("failure_breakdown") or []
    # Show top 5 failure reasons so the message stays compact.
    for reason_code, cnt in breakdown[:5]:
        label = REASON_LABELS.get(reason_code, reason_code)
        breakdown_lines.append(f"   • {escape_md(label)}: `{cnt}`")
    breakdown_block = ""
    if breakdown_lines:
        breakdown_block = (
            "\n*Top Failure Reasons:*\n" + "\n".join(breakdown_lines) + "\n"
        )

    text = (
        "📊 *Bot Statistics*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: `{stats['total_users']}`\n"
        f"📦 Total Orders: `{stats['total_orders']}`\n"
        f"✅ Successful: `{stats['success_orders']}`\n"
        f"⏳ Processing: `{stats['processing_orders']}`\n"
        f"❌ Failed: `{max(failed, 0)}`\n"
        f"🌐 Users With Proxy: `{stats['proxy_users']}`\n"
        f"{breakdown_block}"
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
    stats = await get_stats()

    try:
        db_size = _format_bytes(os.path.getsize(DB_PATH))
    except OSError:
        db_size = "?"

    my_proxy_count = len(await list_user_proxies(message.from_user.id))
    proxy_line = (
        f"🌐 Your Proxies: `{my_proxy_count}` _(rotating)_"
        if my_proxy_count
        else "🌐 Your Proxies: `none` _(direct)_"
    )

    text = (
        "🟢 *Bot Status: ONLINE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: `@{me.username}`\n"
        f"🆔 ID: `{me.id}`\n"
        f"⚡️ API Latency: `{rtt_ms} ms`\n"
        f"⏱ Uptime: `{uptime}`\n"
        f"⏳ Active Orders: `{stats['processing_orders']}`\n"
        f"{proxy_line}\n"
        f"💾 DB Size: `{db_size}`\n"
        f"🐍 Python: `{sys.version.split()[0]}`\n"
        f"💻 Platform: `{platform.system()} {platform.release()}`\n"
        f"📅 Server Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Sab kuch theek chal raha hai!"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("myid", "id", prefix="/."))
async def cmd_myid(message: Message):
    u = message.from_user
    uname = f"@{u.username}" if u.username else "—"
    text = (
        "🆔 *Your Telegram Info*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name: *{escape_md(u.full_name or 'User')}*\n"
        f"🔗 Username: {escape_md(uname)}\n"
        f"🆔 ID: `{u.id}`\n"
        f"🌐 Lang: `{escape_md(u.language_code or '?')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Apni ID copy karke support ya admin ko bhejein._"
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
            name = escape_md(chat.full_name or "Unknown")
            uname = escape_md(f"@{chat.username}") if chat.username else "—"
            lines.append(f"{idx}. *{name}* ({uname}) — `{admin_id}`")
        except Exception:
            lines.append(f"{idx}. _Unknown_ — `{admin_id}`")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Total Admins: `{len(ADMIN_IDS)}`")

    await message.answer("\n".join(lines), parse_mode="Markdown")
