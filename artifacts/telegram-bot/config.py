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

TOPUP_AMOUNTS = [100, 200, 500, 1000, 2000]
MIN_TOPUP = 50

PAYMENT_EASYPAISA = os.environ.get("PAYMENT_EASYPAISA", "0300-XXXXXXX")
PAYMENT_JAZZCASH = os.environ.get("PAYMENT_JAZZCASH", "0301-XXXXXXX")
PAYMENT_ACCOUNT_NAME = os.environ.get("PAYMENT_ACCOUNT_NAME", "Pixel Verification")
