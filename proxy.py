"""User-managed proxy commands.

Each user can register one or more proxies. When a user has at least one
proxy registered, an order's Google login flow is routed through a randomly
chosen entry from their pool (per request).

Commands:

* ``/setproxy``                   — show current proxies (or usage)
* ``/setproxy <url>``             — clear all and set this one as the only proxy
* ``/setproxy off``               — remove all proxies
* ``/addproxy <url>`` (multiline) — append one or more proxies
* ``/removeproxy``                — list with usage
* ``/removeproxy <N|url|all>``    — remove by index, exact URL, or all
* ``/myproxy``                    — short status of current proxies
* ``/proxycheck``                 — verify each proxy by hitting api.ipify.org
"""
from __future__ import annotations

import asyncio
import logging
import time

import requests
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from db import (
    add_user_proxy_url,
    list_user_proxies,
    remove_user_proxy_url,
)
from helpers import escape_md
from proxy_utils import ProxyParseError, normalize_proxy, to_requests_proxies

router = Router()
log = logging.getLogger(__name__)

MAX_PROXIES_PER_USER = 25
PROXY_CHECK_TIMEOUT = 8  # seconds per proxy
PROXY_CHECK_URL = "https://api.ipify.org?format=json"
# Cap concurrent thread-pool slots used by a single /proxycheck call so one
# user's pool of 25 proxies cannot starve aiosqlite or other to_thread work.
_PROXY_CHECK_CONCURRENCY = 5


def _format_proxy_list(plist: list[str], max_show: int = 10) -> str:
    if not plist:
        return "_No proxies set._"
    shown = plist[:max_show]
    lines = [f"  `{i + 1}.` `{escape_md(p)}`" for i, p in enumerate(shown)]
    extra = f"\n  _… +{len(plist) - max_show} more_" if len(plist) > max_show else ""
    return "\n".join(lines) + extra


@router.message(Command("setproxy", prefix="/."))
async def cmd_setproxy(message: Message):
    user_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    if not arg:
        plist = await list_user_proxies(user_id)
        if plist:
            await message.answer(
                f"🌐 *Your Proxies* ({len(plist)})\n\n"
                f"{_format_proxy_list(plist)}\n\n"
                "🔄 _Rotation: random per order_\n\n"
                "*To replace all:* `/setproxy <url>`\n"
                "*To add more:* `/addproxy <url>`\n"
                "*To clear:* `/setproxy off`",
                parse_mode="Markdown",
            )
        else:
            await message.answer(
                "🌐 *No proxy set.*\n\n"
                "*Set one:* `/setproxy http://user:pass@1.2.3.4:8080`\n"
                "*Add multiple:* `/addproxy`\n\n"
                "_Supported: HTTP, HTTPS, SOCKS4, SOCKS5_\n"
                "_Auth supported for HTTP(S). Chromium does not support SOCKS auth._",
                parse_mode="Markdown",
            )
        return

    if arg.lower() in {"off", "none", "remove", "clear"}:
        await remove_user_proxy_url(user_id, None)
        await message.answer(
            "✅ *All proxies cleared.* Direct connection will be used now.",
            parse_mode="Markdown",
        )
        return

    try:
        proxy_url = normalize_proxy(arg)
    except ProxyParseError as e:
        await message.answer(f"⚠️ {escape_md(str(e))}", parse_mode="Markdown")
        return

    await remove_user_proxy_url(user_id, None)
    await add_user_proxy_url(user_id, proxy_url)
    await message.answer(
        "✅ *Proxy set* (replaced all):\n"
        f"`{escape_md(proxy_url)}`\n\n"
        "_Use_ `/addproxy` _to add more for rotation._",
        parse_mode="Markdown",
    )


@router.message(Command("addproxy", prefix="/."))
async def cmd_addproxy(message: Message):
    user_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)
    raw = parts[1].strip() if len(parts) > 1 else ""

    if not raw:
        existing = await list_user_proxies(user_id)
        suffix = f" ({len(existing)} active)" if existing else ""
        await message.answer(
            f"🌐 *Add Proxy{suffix}*\n\n"
            "*Single:*\n"
            "`/addproxy 1.2.3.4:8080`\n"
            "`/addproxy socks5://5.6.7.8:1080`\n"
            "`/addproxy user:pass@9.10.11.12:3128`\n\n"
            "*Multiple* — one per line (or comma-separated):\n"
            "`/addproxy`\n"
            "`1.2.3.4:8080`\n"
            "`socks5://5.6.7.8:1080`\n\n"
            "🔄 _Random rotation per order._",
            parse_mode="Markdown",
        )
        return

    raw_lines = [
        line.strip()
        for line in raw.replace(",", "\n").splitlines()
        if line.strip()
    ]
    if not raw_lines:
        await message.answer("⚠️ Nothing to add.", parse_mode="Markdown")
        return

    existing = await list_user_proxies(user_id)
    remaining_capacity = MAX_PROXIES_PER_USER - len(existing)
    if remaining_capacity <= 0:
        await message.answer(
            f"⚠️ Limit reached. Max `{MAX_PROXIES_PER_USER}` proxies per user. "
            "Use `/removeproxy` first.",
            parse_mode="Markdown",
        )
        return

    added = 0
    dupes = 0
    invalid: list[tuple[str, str]] = []
    for line in raw_lines:
        if added >= remaining_capacity:
            break
        try:
            normalized = normalize_proxy(line)
        except ProxyParseError as e:
            invalid.append((line, str(e)))
            continue
        ok = await add_user_proxy_url(user_id, normalized)
        if ok:
            added += 1
        else:
            dupes += 1

    plist = await list_user_proxies(user_id)
    summary_parts = [f"✅ {added} added"]
    if dupes:
        summary_parts.append(f"⚠️ {dupes} duplicate(s) skipped")
    if invalid:
        summary_parts.append(f"❌ {len(invalid)} invalid")
    if added >= remaining_capacity and len(raw_lines) > added:
        summary_parts.append(f"🔒 cap {MAX_PROXIES_PER_USER} reached")

    text = (
        f"*{' · '.join(summary_parts)}*\n\n"
        f"🌐 *Pool* ({len(plist)} total):\n{_format_proxy_list(plist)}"
    )
    if invalid:
        first = invalid[:3]
        text += "\n\n*Invalid lines:*\n" + "\n".join(
            f"  `{escape_md(line[:40])}` — _{escape_md(reason)}_"
            for line, reason in first
        )
        if len(invalid) > 3:
            text += f"\n  _… +{len(invalid) - 3} more_"
    text += "\n\n_Use_ `/proxycheck` _to test._"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("removeproxy", prefix="/."))
async def cmd_removeproxy(message: Message):
    user_id = message.from_user.id
    plist = await list_user_proxies(user_id)
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    if not plist:
        await message.answer(
            "❌ *No proxies to remove.*\n\nUse `/addproxy` to add one.",
            parse_mode="Markdown",
        )
        return

    if not arg:
        numbered = "\n".join(
            f"  `{i + 1}.` `{escape_md(p)}`" for i, p in enumerate(plist)
        )
        await message.answer(
            f"🗂 *Your Proxies* ({len(plist)})\n{numbered}\n\n"
            "*Usage:*\n"
            "`/removeproxy 2` — remove by number\n"
            "`/removeproxy <full url>` — remove exact match\n"
            "`/removeproxy all` — remove all",
            parse_mode="Markdown",
        )
        return

    if arg.lower() in {"all", "clear"}:
        await remove_user_proxy_url(user_id, None)
        await message.answer(
            f"✅ *All {len(plist)} proxies removed.* Direct connection will be used.",
            parse_mode="Markdown",
        )
        return

    target: str | None = None
    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(plist):
            target = plist[idx]
        else:
            await message.answer(
                f"⚠️ Invalid number. You have `{len(plist)}` proxies (1–{len(plist)}).",
                parse_mode="Markdown",
            )
            return
    else:
        try:
            target = normalize_proxy(arg)
        except ProxyParseError:
            target = arg
        if target not in plist:
            await message.answer(
                "⚠️ That proxy isn't in your pool. Use `/removeproxy` to see the list.",
                parse_mode="Markdown",
            )
            return

    remaining = await remove_user_proxy_url(user_id, target)
    await message.answer(
        f"✅ *Removed:* `{escape_md(target)}`\n"
        f"📊 `{remaining}` remaining.",
        parse_mode="Markdown",
    )


@router.message(Command("myproxy", prefix="/."))
async def cmd_myproxy(message: Message):
    user_id = message.from_user.id
    plist = await list_user_proxies(user_id)
    if not plist:
        await message.answer(
            "🌐 *No proxy configured.* Direct connection will be used for orders.\n\n"
            "_Use_ `/setproxy` _or_ `/addproxy` _to add one._",
            parse_mode="Markdown",
        )
        return
    await message.answer(
        f"🌐 *Active Proxies* ({len(plist)})\n\n{_format_proxy_list(plist)}\n\n"
        "🔄 _One is chosen at random per order._",
        parse_mode="Markdown",
    )


def _check_one_proxy(proxy_url: str) -> tuple[bool, str]:
    """Synchronous proxy probe. Returns (alive, detail)."""
    try:
        start = time.monotonic()
        r = requests.get(
            PROXY_CHECK_URL,
            proxies=to_requests_proxies(proxy_url),
            timeout=PROXY_CHECK_TIMEOUT,
        )
        elapsed = round(time.monotonic() - start, 2)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        try:
            ip = r.json().get("ip", "?")
        except Exception:
            ip = "?"
        return True, f"{ip} ({elapsed}s)"
    except requests.exceptions.ProxyError:
        return False, "Connection failed"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.SSLError:
        return False, "SSL error"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:40]


@router.message(Command("proxycheck", prefix="/."))
async def cmd_proxycheck(message: Message):
    user_id = message.from_user.id
    plist = await list_user_proxies(user_id)
    if not plist:
        await message.answer(
            "❌ *No proxies set.* Use `/addproxy` first.",
            parse_mode="Markdown",
        )
        return

    status_msg = await message.answer(
        f"🔄 *Testing {len(plist)} proxy(ies)…*", parse_mode="Markdown"
    )

    sem = asyncio.Semaphore(_PROXY_CHECK_CONCURRENCY)

    async def _bounded(p: str) -> tuple[bool, str]:
        async with sem:
            return await asyncio.to_thread(_check_one_proxy, p)

    results = await asyncio.gather(*(_bounded(p) for p in plist))

    lines = []
    alive = 0
    for i, (proxy_url, (ok, detail)) in enumerate(zip(plist, results)):
        icon = "✅" if ok else "❌"
        if ok:
            alive += 1
        lines.append(
            f"  {icon} `{i + 1}.` `{escape_md(proxy_url[:42])}` → _{escape_md(detail)}_"
        )

    dead = len(plist) - alive
    summary = f"✅ {alive} alive · ❌ {dead} dead" if dead else f"✅ All {alive} alive"
    body = (
        "🌐 *Proxy Check Results*\n\n"
        + "\n".join(lines)
        + f"\n\n📊 {summary}"
    )

    try:
        await status_msg.edit_text(body, parse_mode="Markdown")
    except TelegramBadRequest:
        await message.answer(body, parse_mode="Markdown")
