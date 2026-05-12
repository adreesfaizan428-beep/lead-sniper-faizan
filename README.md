# 🎯 Lead Sniper — Reddit + Upwork → Telegram Alerts

Monitors public Reddit & Upwork RSS feeds 24/7 for freelance leads matching
your keywords, and sends **instant Telegram alerts** with a quick-copy pitch.

```
Reddit r/forhire ──┐
Reddit r/webdev  ──┤                   ┌─► Your Telegram
Reddit r/shopify ──┼──► Lead Sniper ───┤   (instant alert + pitch)
Upwork Web Dev   ──┤                   └─► Daily report at midnight
Upwork Shopify   ──┘
```

---

## ⚡ Step 1: Create Your Telegram Bot (5 minutes)

### 1a. Create the bot
1. Open Telegram and search for **@BotFather**
2. Send: `/newbot`
3. Choose a name: e.g. `Faizan Lead Sniper`
4. Choose a username: e.g. `faizan_lead_sniper_bot`
5. BotFather will give you a token like:
   ```
   123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```
   → This is your `TELEGRAM_BOT_TOKEN`

### 1b. Get your Chat ID
1. Send any message to your new bot (e.g. "hello")
2. Open this URL in your browser (replace YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Look for `"chat":{"id":XXXXXXXXX}` in the response
4. That number is your `TELEGRAM_CHAT_ID`

---

## 🖥️ Step 2: Local Setup (Test First)

```bash
# Clone / copy the project
cd lead_sniper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
nano .env                        # Fill in your Telegram credentials

# Run it!
python lead_sniper.py
```

You should immediately get a Telegram message:
> 🚀 **Lead Sniper is ONLINE**

---

## ☁️ Step 3: Deploy to VPS (24/7)

### Recommended VPS: DigitalOcean / Hetzner / Vultr
- **Cheapest option:** Hetzner CX11 (~€4/mo) or DigitalOcean Basic ($6/mo)
- OS: Ubuntu 22.04 LTS

### 3a. Initial server setup
```bash
# SSH into your VPS
ssh ubuntu@YOUR_VPS_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
sudo apt install python3 python3-pip python3-venv git -y

# Create project directory
mkdir -p /home/ubuntu/lead_sniper
```

### 3b. Upload your files
```bash
# From your local machine:
scp -r lead_sniper/ ubuntu@YOUR_VPS_IP:/home/ubuntu/
```

### 3c. Set up Python environment on VPS
```bash
cd /home/ubuntu/lead_sniper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env on the server
cp .env.example .env
nano .env    # Add your Telegram credentials
```

### 3d. Install as a systemd service (auto-restart on crash/reboot)
```bash
# Copy service file
sudo cp lead-sniper.service /etc/systemd/system/

# Edit the service file if your username isn't 'ubuntu'
sudo nano /etc/systemd/system/lead-sniper.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable lead-sniper
sudo systemctl start lead-sniper

# Check it's running
sudo systemctl status lead-sniper
```

### 3e. Useful management commands
```bash
# View live logs
sudo journalctl -u lead-sniper -f

# Restart the bot
sudo systemctl restart lead-sniper

# Stop the bot
sudo systemctl stop lead-sniper

# View last 100 log lines
sudo journalctl -u lead-sniper -n 100
```

---

## 📁 Project Structure

```
lead_sniper/
├── lead_sniper.py        # Main bot script
├── requirements.txt      # Python dependencies
├── .env.example          # Credentials template
├── .env                  # Your credentials (never commit this!)
├── lead-sniper.service   # Systemd service file
├── logs/
│   └── lead_sniper.log   # Persistent log file
└── data/
    ├── seen_posts.json   # Tracks already-seen posts (dedup)
    └── daily_stats.json  # Daily metrics for the report
```

---

## 🔧 Customization

### Add more keywords (in `lead_sniper.py`)
```python
KEYWORDS = [
    "shopify", "logo design", "web app", ...
    "your new keyword",   # ← add here
]
```

### Add more Reddit subreddits
```python
REDDIT_FEEDS = [
    ...
    {
        "name": "r/startups",
        "url":  "https://www.reddit.com/r/startups/new/.rss",
        "icon": "🟠",
    },
]
```

### Change scan frequency
```python
SCAN_INTERVAL_SECONDS = 90   # Change to 60 for faster, 120 for slower
```

### Change lookback window
```python
cutoff = datetime.now() - timedelta(minutes=30)  # Change to 60 for older posts
```

---

## 📊 What You'll Receive

### Per Lead Alert:
```
🎯 NEW LEAD DETECTED!

🟠 Source: r/forhire
🕐 Posted: 3m ago
👤 Author: startup_founder_99

📌 Need Shopify expert to build my store from scratch

📝 We have products ready and need someone who...

🔍 Keywords matched: shopify, web developer

🔗 Open Post →

─────────────────────────
📋 QUICK-COPY PITCH:
─────────────────────────
Hi, I'm Faizan – Web Developer & Brand Designer...
```

### Daily Report (midnight):
```
📊 DAILY LEAD SNIPER REPORT
📅 2025-01-15

Posts Scanned:   847
Leads Found:     12
Alerts Sent:     12

Top Keywords:
  • shopify: 5 hits
  • web app: 3 hits
  • logo design: 2 hits

Top Sources:
  • r/forhire: 6 leads
  • Upwork: Shopify: 4 leads
```

---

## ⚠️ Important Notes

- **Reddit RSS**: Fully public, no authentication, no rate limit issues.
  Reddit's own docs encourage RSS usage.
- **Upwork RSS**: Public job feed. If Upwork changes their RSS URLs,
  update them in `UPWORK_FEEDS` in the script.
- **Deduplication**: The bot tracks seen post IDs so you never get
  duplicate alerts for the same post, even across restarts.
- **Upwork note**: Upwork's public RSS sometimes returns limited results.
  For deeper Upwork access, consider their official API (free tier available).

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| No Telegram message on startup | Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` |
| "Chat not found" error | Send a message to your bot first, then get updates |
| No leads appearing | Try broadening keywords or extending `timedelta(minutes=...)` |
| Upwork feed returning nothing | Upwork occasionally blocks scrapers; Reddit feeds will still work |
| Bot stops after VPS reboot | Run `sudo systemctl enable lead-sniper` to enable auto-start |
