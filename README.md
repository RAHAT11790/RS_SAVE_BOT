# Telegram Media Bridge Bot 🤖

A Telegram bot that downloads media from t.me links and uploads them with original format.

## Features ✨
- 📸 Photos as Photos (not documents)
- 🎥 Videos as Videos (with streaming)
- 📄 Documents as Files
- 💬 Preserves original captions
- ☁️ 24/7 Render.com hosting

## Setup 🔧

### 1. Get API Credentials
- **API_ID & API_HASH**: [my.telegram.org](https://my.telegram.org)
- **BOT_TOKEN**: [@BotFather](https://t.me/BotFather)
- **OWNER_ID**: [@userinfobot](https://t.me/userinfobot)

### 2. Deploy on Render.com
1. Fork this repository
2. Go to [render.com](https://render.com)
3. Create new Web Service
4. Connect your GitHub repo
5. Add environment variables:
   - `API_ID`
   - `API_HASH` 
   - `BOT_TOKEN`
   - `OWNER_ID`
   - `SESSION_NAME` (optional)

### 3. Set up UptimeRobot
1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Add HTTP monitor for your Render URL

## Usage 📝

### Commands:
- `/start` - Start bot
- `/login` - Login with phone
- `/logout` - Logout
- `/status` - Check status

### Steps:
1. Send `/login`
2. Enter your phone number (e.g., +8801XXXXXXXXX)
3. Enter verification code
4. Send any t.me link

## Support 💬
Create an issue on GitHub for help.
