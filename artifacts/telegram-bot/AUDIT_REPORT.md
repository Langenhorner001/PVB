# 🔒 Pixel Verification Bot — Forensic Code Audit Report

**Project:** `artifacts/telegram-bot/` (aiogram v3, Python 3.11)
**Audit Date:** 2026-04-21
**Files Reviewed:** 17 `.py` files + `requirements.txt`
**Framework:** aiogram 3.13.0
**Storage:** SQLite (aiosqlite)

---

## 1. Project Map

| File | Purpose |
|------|---------|
| `main.py` | Entry point, middleware + router registration |
| `config.py` | Env-based config (BOT_TOKEN, ADMIN_IDS, payments) |
| `db.py` | All SQLite queries (users, orders, transactions, topup_requests) |
| `google_auth.py` | Sync HTTP-based Google login + partner-link generation |
| `keyboards.py` | All inline & reply keyboards |
| `auth_middleware.py` | Ban-check middleware |
| `throttle_middleware.py` | Per-user rate limiting (1.5 s) |
| `start.py` | `/start` + referral capture |
| `order.py` | FSM order flow (gmail → password → 2FA → confirm) |
| `topup.py` | Stars + Easypaisa/JazzCash top-up flows |
| `balance.py`, `history.py`, `referral.py`, `guide.py`, `contact.py` | Read-only handlers |
| `system.py` | `/help`, `/ping`, `/stats`, `/status`, `/sudo_users` |
| `admin.py` | Admin panel + broadcast + balance/ban management |

---

## 2. Issue Table

| # | Severity | Category | File | Line | Description | Fix Applied |
|---|----------|----------|------|------|-------------|-------------|
| 1 | **CRITICAL** | Logic / Safety | `db.py` | 176 | `add_balance()` accepts any integer including negatives — silent subtraction without balance check, can drive balance below zero. | Added `if amount <= 0: raise ValueError`. |
| 2 | **CRITICAL** | Idempotency / Money | `topup.py` | 145 | `successful_payment` handler has no idempotency check — Telegram can deliver the same event twice (e.g. on webhook retry), causing duplicate credits. | Added `processed_payments` table + check on `telegram_payment_charge_id`. |
| 3 | **HIGH** | Anti-flood / Bot ban risk | `admin.py` | 76 | Broadcast loops over all users without throttling. Telegram limits ~30 msgs/sec — bot will be flood-throttled and may be temporarily banned. | Added `asyncio.sleep(0.05)` per message + `TelegramRetryAfter` handling. |
| 4 | **HIGH** | Markdown injection | `order.py` 200, `topup.py` 192, `system.py` 161 | — | User-controlled `full_name`/`username` injected into Markdown — can break message rendering or impersonate (`*evil*`). | Added `escape_md()` helper; applied to all admin notification interpolations. |
| 5 | **HIGH** | Crash on non-text input | `order.py` 67, 83, 100 | — | Direct `message.text.strip()` without None check — sticker/photo crashes handler with `AttributeError`. | Added text-presence guards. |
| 6 | **HIGH** | Middleware coverage gap | `main.py` 41 | — | Ban-check + throttle middleware bound only to `dp.message`, not `dp.callback_query` — banned users can still trigger inline buttons; rate limit bypassed. | Bound both middlewares to `callback_query` too. |
| 7 | **HIGH** | Deprecated API | `order.py` 171 | — | `asyncio.get_event_loop()` is deprecated in Python 3.10+. | Replaced with `asyncio.to_thread()`. |
| 8 | **HIGH** | Unhandled JSON decode | `google_auth.py` 110 | — | `api_r.json()` raises `JSONDecodeError` if response is HTML — wrapped only by outer broad except, masking real error. | Added explicit try/except returning structured error. |
| 9 | **MEDIUM** | Dependency pinning | `requirements.txt` | 2-5 | `pyotp`, `aiosqlite`, `aiohttp`, `requests` unpinned — reproducibility risk. | Pinned all to current resolved versions. |
| 10 | **MEDIUM** | Markdown text concat | `topup.py` 417, 466 | — | `callback.message.text + ...` then re-parsed as Markdown — strips formatting and can crash if any `_*[]` chars exist. | Replaced with `edit_caption`-style append using HTML-safe text + parse_mode=None for the appended status line. |
| 11 | **MEDIUM** | Race in user creation | `db.py` 161 | — | Two simultaneous `/start` calls from a new user with referral can double-credit referrer (referral check + INSERT OR IGNORE not atomic). | Moved referral bonus inside `INSERT OR IGNORE` rowcount check. |
| 12 | **MEDIUM** | Admin add-balance validation | `admin.py` 105 | — | No upper bound or positive check — admin typo of `0` or huge number passes through. | Added range check (1–1,000,000). |
| 13 | **LOW** | Misleading metric | `system.py` 92 | — | `cmd_ping` measures local code time, not RTT — labeled "Latency" but only times the `await message.answer()` call. | Acceptable; the `await` includes the network round-trip to Telegram, so it is the closest available proxy for RTT. **No change.** |
| 14 | **LOW** | Cached `bot.get_me()` | `referral.py` 19 | — | Called on every request; should cache username. | Cached at module level on first call. |
| 15 | **LOW** | Bare-ish broad excepts | multiple | — | Several `except Exception: pass` swallow errors silently. | Replaced no-op excepts with `logger.warning(...)` where it aids debugging. |
| 16 | **LOW** | Logging of sensitive data | `order.py` | — | Bot does **not** log Google password or 2FA secret anywhere. State stored in `MemoryStorage` and cleared after use. | **Verified clean — no fix needed**, but added explicit `# do-not-log` comment near sensitive vars. |
| 17 | **LOW** | Webhook secret token | n/a | — | Bot uses `start_polling` (no webhook), so webhook-secret-token bypass is N/A. | **No fix needed**. |
| 18 | **LOW** | Hardcoded secrets | `config.py` | 1-5 | `BOT_TOKEN` and `ADMIN_IDS` are read from `os.environ` ✅. No hardcoded secrets found. | **Verified clean — no fix needed**. |
| 19 | **LOW** | SQL injection | `db.py` (all) | — | All queries use parameterized `?` placeholders ✅. | **Verified clean — no fix needed**. |
| 20 | **LOW** | Command injection | n/a | — | No `os.system`, `subprocess`, `eval`, `exec`, or `pickle` usage anywhere ✅. | **Verified clean — no fix needed**. |

---

## 3. Severity Breakdown

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 6 |
| Medium | 4 |
| Low (verified clean / no-op) | 8 |
| **Total findings** | **20** |
| **Total fixed** | **12** |

---

## 4. Notes & Out-of-Scope

- **`google_auth.py` HTTP login** is fundamentally fragile — Google does not expose a public username/password+TOTP login API. The current regex-scraping approach will not survive any Google UI change. Replacing it with browser automation is **already tracked as Task #3** and intentionally out of scope per the audit's `do_not_touch` clause ("do not change core business logic").
- **MemoryStorage for FSM** means in-progress orders are lost on bot restart. Switching to `RedisStorage` or `SQLAlchemyStorage` is a behavior-changing refactor; flagged but **not applied**.
- **Connection-per-query** in `db.py` is suboptimal but safe; switching to a connection pool is a perf optimization, **not applied**.

See `CHANGES.md` for the per-file diff summary and `.env.example` for required environment variables.
