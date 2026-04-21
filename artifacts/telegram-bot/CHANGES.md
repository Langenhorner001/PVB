# Changes — Audit Hardening (2026-04-21)

| File | Change |
|------|--------|
| `helpers.py` | **NEW** — `escape_md()` helper for safe Markdown V1 interpolation. |
| `db.py` | Added `processed_payments` table; new `record_payment()` for Stars idempotency; `add_balance()` now rejects non-positive amounts. |
| `main.py` | `BanCheckMiddleware` and `ThrottleMiddleware` now also bound to `dp.callback_query`. |
| `auth_middleware.py` | Handles both `Message` and `CallbackQuery`. |
| `throttle_middleware.py` | Handles both `Message` and `CallbackQuery`. |
| `order.py` | Added `message.text` None-guards on all 3 FSM steps; replaced deprecated `asyncio.get_event_loop()` with `asyncio.to_thread()`; escaped `full_name` / `gmail` / `error` in admin notifications; added `do-not-log` markers near sensitive vars. |
| `admin.py` | Broadcast: throttled (~20/sec) + handles `TelegramRetryAfter` / `TelegramForbiddenError`; reports blocked count. Add/deduct balance: validate range (1–1,000,000) and `message.text` None. |
| `topup.py` | Stars `successful_payment`: idempotency guard via `record_payment()`; admin approve/reject: safe Markdown via `escape_md()` + None-guard on `callback.message.text`. |
| `google_auth.py` | `api_r.json()` wrapped with explicit `JSONDecodeError` handler. |
| `system.py` | Sudo-users list escapes admin names/usernames. |
| `referral.py` | Cached `bot.get_me()` username instead of per-request fetch. |
| `requirements.txt` | Pinned all transitive deps to current resolved versions. |
| `AUDIT_REPORT.md` | **NEW** — full forensic findings. |
| `.env.example` | **NEW** — required + optional env vars. |

## Behaviour preserved
- All commands, FSM flows, top-up methods, referral logic, admin bypass — unchanged.
- All user-facing text remains in Roman Urdu where it was.
- No commands renamed, no features removed.
