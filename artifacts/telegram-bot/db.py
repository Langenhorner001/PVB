import aiosqlite
import uuid
from datetime import datetime
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                created_at TEXT,
                is_banned INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                gmail TEXT,
                status TEXT DEFAULT 'pending',
                generated_link TEXT,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id)
            )
        """)
        await db.commit()


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(telegram_id: int, username: str, full_name: str, referred_by_code: str = None):
    ref_code = str(uuid.uuid4())[:8].upper()
    referred_by = None

    if referred_by_code:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT telegram_id FROM users WHERE referral_code = ?", (referred_by_code,)
            ) as cursor:
                ref_row = await cursor.fetchone()
                if ref_row:
                    referred_by = ref_row["telegram_id"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users 
               (telegram_id, username, full_name, balance, referral_code, referred_by, created_at, is_banned)
               VALUES (?, ?, ?, 0, ?, ?, ?, 0)""",
            (telegram_id, username, full_name, ref_code, referred_by, datetime.now().isoformat()),
        )
        await db.commit()
    return ref_code, referred_by


async def get_or_create_user(telegram_id: int, username: str, full_name: str, ref_code: str = None):
    user = await get_user(telegram_id)
    if not user:
        referral_code, referred_by = await create_user(telegram_id, username, full_name, ref_code)
        if referred_by:
            await add_balance(referred_by, 10, "referral", f"Referral bonus from {full_name}")
        user = await get_user(telegram_id)
    return user


async def get_balance(telegram_id: int) -> int:
    user = await get_user(telegram_id)
    return user["balance"] if user else 0


async def add_balance(telegram_id: int, amount: int, tx_type: str, description: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, amount, tx_type, description, datetime.now().isoformat()),
        )
        await db.commit()


async def deduct_balance(telegram_id: int, amount: int, tx_type: str, description: str) -> bool:
    user = await get_user(telegram_id)
    if not user or user["balance"] < amount:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance - ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, -amount, tx_type, description, datetime.now().isoformat()),
        )
        await db.commit()
    return True


async def create_order(user_id: int, gmail: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, gmail, status, created_at) VALUES (?, ?, 'processing', ?)",
            (user_id, gmail, datetime.now().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def update_order(order_id: int, status: str, link: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ?, generated_link = ? WHERE id = ?",
            (status, link, order_id),
        )
        await db.commit()


async def get_orders(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT telegram_id FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [r["telegram_id"] for r in rows]


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders") as c:
            total_orders = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'success'") as c:
            success_orders = (await c.fetchone())[0]
    return {"total_users": total_users, "total_orders": total_orders, "success_orders": success_orders}


async def ban_user(telegram_id: int, banned: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = ? WHERE telegram_id = ?",
            (1 if banned else 0, telegram_id),
        )
        await db.commit()


async def get_referral_count(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?", (telegram_id,)
        ) as c:
            return (await c.fetchone())[0]
