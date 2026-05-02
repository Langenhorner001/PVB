# Pixel Verification Bot

> A self-hosted Telegram bot for Pixel phone Google One offer verification, built for operators who need speed, control, history, payments, referrals, proxies, and clean EC2 deployment in one focused Python project.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Local_DB-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![EC2](https://img.shields.io/badge/AWS_EC2-Ready-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)

---

## The Idea

Pixel Verification Bot is made for one simple mission:

**make Pixel offer verification faster, cleaner, trackable, and easier to run 24/7.**

Instead of manually handling every user, every Google login flow, every balance request, every proxy issue, and every order history check, this bot turns the whole process into a smooth Telegram experience.

Users get a simple bot interface.
Admins get control.
The service gets automation.
And your EC2 server keeps it alive day and night.

---

## What This Bot Does

This bot helps users submit Pixel/Google One verification orders through Telegram. It uses Playwright Chromium to automate the Google login flow and generate the required `partner-eft-onboard` link.

It also includes a full mini business layer around the verification flow:

- User balance and credit system
- Per-order cost control
- Referral rewards
- Manual top-up flow
- Admin panel
- Broadcast system
- User ban/unban tools
- Order history
- Proxy support per user
- Failure reason tracking
- Health/status commands
- SQLite database storage
- EC2 systemd deployment
- GitHub Actions auto-deploy

This is not just a script. It is a small operating system for running the service properly.

---

## Why It Matters

Manual verification work gets messy fast.

Users ask for status.
Admins lose track of balances.
Failed orders need reasons.
Proxy quality changes.
Payments need proof.
The bot needs to stay online.
And every update should not require ten annoying commands.

Pixel Verification Bot solves those problems by giving you:

**Speed**  
Orders are handled through a guided Telegram flow.

**Control**  
Admins can manage users, balances, bans, broadcasts, and stats.

**Trust**  
Users can check their balance, history, referral rewards, and top-up options.

**Visibility**  
Failures are categorized, so admins can see what is going wrong.

**Stability**  
The bot runs as a systemd service on EC2 and restarts automatically.

**Automation**  
Push to GitHub, and EC2 can update itself through GitHub Actions.

---

## Main Features

### User Features

- `/start` onboarding flow
- Place verification orders
- Check balance
- View order history
- Contact support
- Referral earning system
- Manual top-up instructions
- Proxy setup commands:
  - `/setproxy`
  - `/addproxy`
  - `/removeproxy`
  - `/myproxy`
  - `/proxycheck`
- `/myid` to get Telegram user ID

### Admin Features

- Admin panel through `/admin`
- Add user balance
- Deduct user balance
- Ban users
- Unban users
- Broadcast messages
- View bot stats
- View failure reasons
- Monitor processing orders
- Check database size and health

### Automation Features

- Google login automation with Playwright Chromium
- Proxy-aware login flow
- SQLite persistence
- Failure categorization
- systemd service generation
- EC2 one-command setup
- GitHub Actions auto-deploy

---

## Project Structure

The project is intentionally flat and simple now:

```text
.
|-- main.py                    # Bot entry point
|-- config.py                  # Runtime config and .env loader
|-- db.py                      # SQLite database layer
|-- google_auth.py             # Google login and link generation
|-- order.py                   # Order flow
|-- proxy.py                   # Proxy commands
|-- proxy_utils.py             # Proxy parsing/adapters
|-- admin.py                   # Admin panel logic
|-- topup.py                   # Top-up flow
|-- balance.py                 # Balance commands
|-- history.py                 # Order history
|-- referral.py                # Referral system
|-- system.py                  # Status/stats commands
|-- keyboards.py               # Telegram keyboards
|-- requirements.txt           # Bot runtime dependencies
|-- requirements-deploy.txt    # Optional deploy helper dependencies
|-- setup.sh                   # EC2 installer
|-- deploy.py                  # Optional Python deploy helper
|-- push.py                    # GitHub push helper
|-- scripts/
|   `-- ec2-deploy.sh          # Runs on EC2 after GitHub Actions sync
`-- .github/workflows/
    `-- deploy-ec2.yml         # Auto-deploy workflow
```

Runtime files such as `.env`, `bot_data.db`, virtualenvs, cache folders, and private SSH keys are intentionally ignored by git.

---

## Requirements

For local or EC2 runtime:

- Ubuntu 22.04 or 24.04 recommended
- Python 3.11+
- Telegram bot token from `@BotFather`
- Telegram admin user ID from `@userinfobot`
- Playwright Chromium
- systemd for production EC2 deployment

Python dependencies are listed in:

```bash
requirements.txt
```

---

## Environment Variables

Create a `.env` file from `.env.example`, or let `setup.sh` create it during EC2 install.

Required:

```env
BOT_TOKEN=123456:ABC_your_bot_token
ADMIN_ID=123456789
```

Optional:

```env
ADMIN_IDS=123456789,987654321
PAYMENT_EASYPAISA=0300-XXXXXXX
PAYMENT_JAZZCASH=0301-XXXXXXX
PAYMENT_ACCOUNT_NAME=Pixel Verification
```

For GitHub push/deploy helper:

```env
GITHUB_TOKEN=your_github_token
GITHUB_REMOTE=https://github.com/your-user/your-repo.git
GITHUB_BRANCH=main
```

Your GitHub token must have permission to push workflow files:

- Classic PAT: `repo` + `workflow`
- Fine-grained token: `Contents: Read and write` + `Workflows: Read and write`

---

## Run Locally

Install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Create `.env`:

```bash
cp .env.example .env
nano .env
```

Run the bot:

```bash
python main.py
```

---

## Deploy on EC2 / Linux VPS

This project includes a full EC2/Linux VPS installer. It installs packages, creates a Python virtual environment, installs dependencies, installs Playwright Chromium, writes `.env`, creates a systemd service, and starts the bot.

### 1. Connect to the Server

Key-based server:
```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Password-based VPS:
```bash
ssh root@YOUR_VPS_IP
```

### 2. Install Git and Clone the Repo

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git PVB
cd PVB
```

### 3. Run Setup

Interactive mode:

```bash
bash setup.sh
```

The script will ask for:

```text
BOT_TOKEN
ADMIN_ID
```

Non-interactive mode:

```bash
BOT_TOKEN="123456:ABC" ADMIN_ID="123456789" bash setup.sh
```

If running with sudo:

```bash
sudo BOT_TOKEN="123456:ABC" ADMIN_ID="123456789" bash setup.sh
```

### 4. Check Service

```bash
sudo systemctl status pixel-bot
```

Live logs:

```bash
journalctl -u pixel-bot -f
```

Restart:

```bash
sudo systemctl restart pixel-bot
```

Stop:

```bash
sudo systemctl stop pixel-bot
```

---

## Auto-Deploy to EC2 After Git Push

The repo includes GitHub Actions auto-deploy:

```text
.github/workflows/deploy-ec2.yml
```

When you push to `main`, GitHub Actions will:

1. SSH into EC2
2. Go to your repo path
3. Run `git fetch origin main`
4. Run `git reset --hard origin/main`
5. Run `scripts/ec2-deploy.sh`
6. Copy bot files into the service directory
7. Preserve `.env`, `bot_data.db`, `venv`, and Playwright cache
8. Install/update dependencies
9. Restart `pixel-bot`

This avoids the common EC2 error:

```text
fatal: Need to specify how to reconcile divergent branches
```

because deployment uses `fetch + reset`, not `git pull`.

### GitHub Secrets Needed

In your GitHub repo, go to:

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

Add:

```text
EC2_HOST       = your EC2 public IP
```

Then choose one auth method:

```text
EC2_SSH_KEY    = private SSH key in OpenSSH format
```

or for password-based VPS:

```text
EC2_PASSWORD   = VPS SSH password
```

Optional:

```text
EC2_USER       = ubuntu or root
EC2_PORT       = 22
EC2_REPO_PATH  = /home/ubuntu/PVB
EC2_SERVICE    = pixel-bot
BOT_DIR        = /home/ubuntu/pixel-bot
EC2_SUDO_PASSWORD = sudo password, only if different from EC2_PASSWORD
```

After that, deploy becomes:

```bash
git add -A
git commit -m "Update bot"
git push origin main
```

GitHub Actions handles the EC2 update.

---

## Important EC2 Paths

Recommended repo path:

```text
/home/ubuntu/PVB
```

Recommended service/app path:

```text
/home/ubuntu/pixel-bot
```

Runtime env file:

```text
/home/ubuntu/pixel-bot/.env
```

SQLite database:

```text
/home/ubuntu/pixel-bot/bot_data.db
```

Systemd unit:

```text
/etc/systemd/system/pixel-bot.service
```

---

## Database and Backups

The bot uses SQLite:

```text
bot_data.db
```

This file contains important runtime data such as:

- Users
- Balances
- Orders
- Referrals
- Top-up records
- Proxy records
- History

Back it up regularly:

```bash
cp /home/ubuntu/pixel-bot/bot_data.db ~/bot_data_backup_$(date +%F).db
```

Do not commit `bot_data.db` to GitHub.

---

## Security Notes

- Never commit `.env`
- Never commit `.pem` or `.ppk` private keys
- Use a dedicated Telegram bot token
- Keep your GitHub PAT private
- Prefer GitHub Actions secrets for EC2 keys
- Keep `bot_data.db` private because it contains user/order data
- Rotate tokens if they appear in screenshots or logs

---

## Useful Commands

Check service:

```bash
sudo systemctl status pixel-bot
```

Restart service:

```bash
sudo systemctl restart pixel-bot
```

Live logs:

```bash
journalctl -u pixel-bot -f
```

Show recent logs:

```bash
journalctl -u pixel-bot -n 100 --no-pager
```

Update manually on EC2:

```bash
cd /home/ubuntu/PVB
git fetch origin main
git reset --hard origin/main
bash scripts/ec2-deploy.sh
```

---

## Troubleshooting

### BOT_TOKEN is missing

Edit the EC2 env file:

```bash
nano /home/ubuntu/pixel-bot/.env
```

Then restart:

```bash
sudo systemctl restart pixel-bot
```

### GitHub push says workflow scope is missing

Your token cannot push `.github/workflows/deploy-ec2.yml`.

Use a classic GitHub PAT with:

```text
repo
workflow
```

### GitHub push says invalid username or token

Your token is expired, wrong, missing, or overridden by an old environment variable.

Check `.env`:

```env
GITHUB_TOKEN=your_new_token
GITHUB_REMOTE=https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

Then run:

```bash
python push.py "Update bot"
```

### EC2 says divergent branches

Use:

```bash
git fetch origin main
git reset --hard origin/main
```

The auto-deploy workflow already does this.

### Playwright browser issue

Run:

```bash
cd /home/ubuntu/pixel-bot
source venv/bin/activate
playwright install chromium
sudo systemctl restart pixel-bot
```

---

## Final Note

Pixel Verification Bot is built to reduce stress.

It gives users a cleaner experience, gives admins a stronger dashboard, and gives the server a dependable deployment path. The goal is simple: less manual work, fewer mistakes, faster service, and a bot that feels professional from the first `/start` to the final completed order.
