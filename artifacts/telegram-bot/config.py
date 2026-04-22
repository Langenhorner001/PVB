import os
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID_RAW = os.environ.get("ADMIN_ID", "")
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "")

ADMIN_IDS = []
if ADMIN_ID_RAW.strip().isdigit():
    ADMIN_IDS.append(int(ADMIN_ID_RAW.strip()))
ADMIN_IDS.extend(
    int(x.strip())
    for x in ADMIN_IDS_RAW.split(",")
    if x.strip().isdigit()
    and int(x.strip()) not in ADMIN_IDS
)

DB_PATH = "bot_data.db"

ORDER_COST = 40
REFERRAL_REWARD = 10
INITIAL_BALANCE = 0

SUPPORT_USERNAME = "@PixelVerifySupport"
BOT_NAME = "Pixel Verification Bot"

TOPUP_AMOUNTS = [100, 200, 500, 1000, 2000]
MIN_TOPUP = 50

PAYMENT_EASYPAISA = os.environ.get("PAYMENT_EASYPAISA", "0300-XXXXXXX")
PAYMENT_JAZZCASH = os.environ.get("PAYMENT_JAZZCASH", "0301-XXXXXXX")
PAYMENT_ACCOUNT_NAME = os.environ.get("PAYMENT_ACCOUNT_NAME", "Pixel Verification")

TOPUP_PACKAGES = [
    {"id": "pkg_50",  "credits": 50,  "stars": 50,  "label": "50 Credits",  "emoji": "🥉"},
    {"id": "pkg_100", "credits": 100, "stars": 95,  "label": "100 Credits", "emoji": "🥈"},
    {"id": "pkg_250", "credits": 250, "stars": 225, "label": "250 Credits", "emoji": "🥇"},
    {"id": "pkg_500", "credits": 500, "stars": 425, "label": "500 Credits", "emoji": "💎"},
]
