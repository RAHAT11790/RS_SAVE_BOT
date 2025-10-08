#!/usr/bin/env python3
"""
Telebridge - Flask + Telethon (User-login + Bot-forward)
"""

import os
import re
import asyncio
import tempfile
import logging
from flask import Flask, request, jsonify
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# ---------------- CONFIG ----------------
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_NAME = os.environ.get("SESSION_NAME", "user_session")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 2*1024*1024*1024))
PORT = int(os.environ.get("PORT", "5000"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("telebridge")

# Flask App
app = Flask(__name__)

# Telethon user client
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
loop = asyncio.get_event_loop()

# Bot forward client
from telethon.sync import TelegramClient as BotClient
bot = BotClient('bot', 0, '', bot_token=BOT_TOKEN)

# Login state
STATE = {"awaiting": None, "phone": None, "phone_code_hash": None, "logged_in": False}

# Sequential queue
link_queue = asyncio.Queue()
processing = False

# ---------------- TELETHON HELPERS ----------------

async def download_and_forward(link):
    """Download from user account and forward to bot chat."""
    try:
        m = re.search(r"https?://t\.me/((?:c/)?(\d+|[A-Za-z0-9_]+)/(\d+))", link)
        if not m:
            return {"ok": False, "msg": f"Invalid t.me link: {link}"}

        full_path = m.group(1)
        chat_part = m.group(2)
        msg_id = int(m.group(3))

        # Determine chat id
        if full_path.startswith("c/"):
            from_chat = int("-100" + chat_part)
        else:
            from_chat = chat_part if chat_part.startswith("@") else f"@{chat_part}"

        # Temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            dest_path = tmp.name

        logger.info(f"Fetching message {msg_id} from {from_chat}...")
        msg = await client.get_messages(from_chat, ids=msg_id)
        if not msg:
            return {"ok": False, "msg": f"Message {msg_id} not found"}
        if not msg.media:
            return {"ok": False, "msg": f"No media. Text: {msg.text or '(empty)'}"}

        # Download
        logger.info("Downloading media...")
        path = await client.download_media(msg, file=dest_path)

        file_size = os.path.getsize(path)
        if file_size > MAX_FILE_SIZE:
            os.unlink(path)
            return {"ok": False, "msg": f"File too large ({file_size / (1024**2):.2f} MB)"}

        caption = msg.text or ""

        # Forward via bot
        if msg.photo:
            await bot.send_file(bot.get_me().id, path, caption=caption)
            media_type = "photo"
        elif msg.video:
            await bot.send_file(bot.get_me().id, path, caption=caption)
            media_type = "video"
        else:
            await bot.send_file(bot.get_me().id, path, caption=caption)
            media_type = "document"

        os.unlink(path)
        return {"ok": True, "msg": f"{media_type} forwarded ({file_size / (1024**2):.2f} MB)"}

    except Exception as e:
        logger.exception("Error in download_and_forward")
        return {"ok": False, "msg": str(e)}

async def process_queue():
    global processing
    if processing:
        return
    processing = True
    while not link_queue.empty():
        link = await link_queue.get()
        result = await download_and_forward(link)
        logger.info(result.get("msg"))
    processing = False

# ---------------- FLASK ROUTES ----------------

@app.route("/ping")
def ping():
    return "alive", 200

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    phone = data.get("phone")
    if not phone:
        return jsonify({"ok": False, "error": "phone required"}), 400
    try:
        phone_code_hash = loop.run_until_complete(client.send_code_request(phone))
        STATE.update({"phone": phone, "phone_code_hash": phone_code_hash, "awaiting": "code"})
        return jsonify({"ok": True, "status": "code_sent"})
    except Exception as e:
        logger.exception("send_code_request failed")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/verify", methods=["POST"])
def verify():
    if STATE.get("awaiting") != "code":
        return jsonify({"ok": False, "error": "not expecting code"}), 400
    data = request.get_json() or {}
    code = data.get("code")
    if not code:
        return jsonify({"ok": False, "error": "code required"}), 400
    try:
        res = loop.run_until_complete(client.sign_in(phone=STATE["phone"], code=code, phone_code_hash=STATE["phone_code_hash"]))
        STATE.update({"logged_in": True, "awaiting": None})
        me = loop.run_until_complete(client.get_me())
        return jsonify({"ok": True, "status": "logged_in", "me": {"id": me.id, "name": me.first_name}})
    except SessionPasswordNeededError:
        STATE["awaiting"] = "password"
        return jsonify({"ok": True, "status": "2fa_required"}), 200
    except Exception as e:
        logger.exception("verify failed")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/password", methods=["POST"])
def password():
    if STATE.get("awaiting") != "password":
        return jsonify({"ok": False, "error": "not expecting password"}), 400
    data = request.get_json() or {}
    pwd = data.get("password")
    if not pwd:
        return jsonify({"ok": False, "error": "password required"}), 400
    try:
        loop.run_until_complete(client.sign_in(password=pwd))
        STATE.update({"logged_in": True, "awaiting": None})
        me = loop.run_until_complete(client.get_me())
        return jsonify({"ok": True, "status": "logged_in", "me": {"id": me.id, "name": me.first_name}})
    except Exception as e:
        logger.exception("password sign-in failed")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/enqueue", methods=["POST"])
def enqueue():
    if not STATE.get("logged_in"):
        return jsonify({"ok": False, "error": "not logged in"}), 400
    data = request.get_json() or {}
    links = data.get("links") or []
    if not links:
        return jsonify({"ok": False, "error": "no links provided"}), 400
    for link in links:
        link_queue.put_nowait(link)
    asyncio.ensure_future(process_queue())
    return jsonify({"ok": True, "status": "queued", "links_added": len(links)}), 200

# ---------------- START ----------------

async def _start_clients():
    await client.start()
    await bot.start()
    logger.info("Clients started")
    import threading
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(_start_clients())
