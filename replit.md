# Workspace

## Overview

pnpm workspace monorepo using TypeScript, with a Python Telegram bot service.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM (Node.js side)
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)
- **Python version**: 3.11 (for Telegram bot)

## Telegram Bot (`artifacts/telegram-bot/`)

A Python Telegram bot (aiogram v3) for Pixel phone Google One offer verification.

### Features
- **Place Order**: User provides Gmail + password + 2FA secret → bot logs in and generates Google One partner-eft-onboard link
- **Balance**: Credit system (each order costs 40 credits)
- **Refer & Earn**: Unique referral links, 10 credits per referral
- **History**: Past order history with status
- **Guide**: Step-by-step usage instructions
- **Contact Support**: Support contact info
- **Admin Panel** (`/admin`): Broadcast, add/deduct balance, ban/unban users, view stats

### Bot Config
- `BOT_TOKEN` — from Replit Secrets
- `ADMIN_IDS` — comma-separated Telegram user IDs from Replit Secrets
- Database: SQLite (`bot_data.db` in the bot directory)
- Workflow: "Telegram Bot" runs `cd artifacts/telegram-bot && python main.py`

### Key Files
- `artifacts/telegram-bot/main.py` — entry point
- `artifacts/telegram-bot/config.py` — settings
- `artifacts/telegram-bot/db.py` — SQLite database layer
- `artifacts/telegram-bot/google_auth.py` — Google login & link generation
- `artifacts/telegram-bot/keyboards.py` — Telegram keyboard layouts
- `artifacts/telegram-bot/handlers/` — all command/message handlers
- `artifacts/telegram-bot/middlewares/auth.py` — ban check middleware

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
