import aiosqlite
import uuid
from datetime import datetime
from config import DB_PATH, REFERRAL_REWARD, INITIAL_BALANCE


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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_payments (
                charge_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topup_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                payment_method TEXT,
                transaction_ref TEXT,
                status TEXT DEFAULT 'pending',
                admin_note TEXT,
                created_at TEXT,
                processed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id)
            )
        """)
        await db.commit()


async def create_topup_request(user_id: int, amount: int, payment_method: str, transaction_ref: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO topup_requests (user_id, amount, payment_method, transaction_ref, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (user_id, amount, payment_method, transaction_ref, datetime.now().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_topup_request(request_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM topup_requests WHERE id = ?", (request_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_topup_status(request_id: int, status: str, admin_note: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE topup_requests SET status = ?, admin_note = ?, processed_at = ? WHERE id = ?",
            (status, admin_note, datetime.now().isoformat(), request_id),
        )
        await db.commit()


async def claim_topup_request(request_id: int, new_status: str, admin_note: str) -> bool:
    """Atomically transition a topup_request from 'pending' to new_status.
    Returns True only if this call was the one that performed the transition."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE topup_requests
               SET status = ?, admin_note = ?, processed_at = ?
               WHERE id = ? AND status = 'pending'""",
            (new_status, admin_note, datetime.now().isoformat(), request_id),
        )
        await db.commit()
        return cursor.rowcount == 1


async def get_pending_topups(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM topup_requests WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_topups(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM topup_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


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
               VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
            (telegram_id, username, full_name, INITIAL_BALANCE, ref_code, referred_by, datetime.now().isoformat()),
        )
        await db.commit()
    return ref_code, referred_by


async def get_or_create_user(telegram_id: int, username: str, full_name: str, ref_code: str = None):
    user = await get_user(telegram_id)
    if not user:
        referral_code, referred_by = await create_user(telegram_id, username, full_name, ref_code)
        if referred_by:
            await add_balance(referred_by, REFERRAL_REWARD, "referral", f"Referral bonus from {full_name}")
        user = await get_user(telegram_id)
    return user


async def get_balance(telegram_id: int) -> int:
    user = await get_user(telegram_id)
    return user["balance"] if user else 0


async def record_payment(charge_id: str, user_id: int, amount: int) -> bool:
    """Idempotency guard for Telegram successful_payment events.
    Returns True if this charge_id was newly recorded, False if already processed."""
    if not charge_id:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO processed_payments (charge_id, user_id, amount, created_at) VALUES (?, ?, ?, ?)",
            (charge_id, user_id, amount, datetime.now().isoformat()),
        )
        await db.commit()
        return cursor.rowcount == 1


async def add_balance(telegram_id: int, amount: int, tx_type: str, description: str):
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError(f"add_balance: amount must be a positive integer, got {amount!r}")
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


async def get_order_by_id(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, u.username, u.full_name
               FROM orders o
               LEFT JOIN users u ON o.user_id = u.telegram_id
               WHERE o.id = ?""",
            (order_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_recent_orders(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, u.username, u.full_name
               FROM orders o
               LEFT JOIN users u ON o.user_id = u.telegram_id
               ORDER BY o.created_at DESC LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def search_orders(query: str, limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = query.strip()
        if query.isdigit():
            async with db.execute(
                """SELECT o.*, u.username, u.full_name
                   FROM orders o
                   LEFT JOIN users u ON o.user_id = u.telegram_id
                   WHERE o.user_id = ? OR o.id = ?
                   ORDER BY o.created_at DESC LIMIT ?""",
                (int(query), int(query), limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            pattern = f"%{query}%"
            async with db.execute(
                """SELECT o.*, u.username, u.full_name
                   FROM orders o
                   LEFT JOIN users u ON o.user_id = u.telegram_id
                   WHERE o.gmail LIKE ?
                   ORDER BY o.created_at DESC LIMIT ?""",
                (pattern, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def refund_order(order_id: int, order_cost: int) -> bool:
    """Refund an order: restore credits to user and mark as refunded.
    Returns True if the order was found and refunded, False otherwise."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        order = dict(row)
        if order["status"] == "refunded":
            return False
        cursor = await db.execute(
            "UPDATE orders SET status = 'refunded' WHERE id = ? AND status != 'refunded'",
            (order_id,),
        )
        if cursor.rowcount == 0:
            await db.commit()
            return False
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (order_cost, order["user_id"]),
        )
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (order["user_id"], order_cost, "refund", f"Admin refund for Order #{order_id}", datetime.now().isoformat()),
        )
        await db.commit()
    return True
