import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

DB_PATH = "bot_data.db"

ORDER_COST = 40
REFERRAL_REWARD = 10
INITIAL_BALANCE = 0

SUPPORT_USERNAME = "@PixelVerifySupport"
BOT_NAME = "Pixel Verification Bot"
