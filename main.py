"""
Telegram Video Downloader Bot
------------------------------
Sends /start -> greeting.
Sends any message containing a link -> bot downloads the video with yt-dlp
and sends it back to the user in the chat.

Supports most sites yt-dlp supports (YouTube, TikTok, Facebook, Instagram,
Twitter/X, etc.) as long as the content is publicly accessible.

Env vars required:
    BOT_TOKEN   - Telegram bot token from @BotFather

Optional env vars:
    PORT        - port for the tiny health-check HTTP server (Koyeb needs
                  a listening port for "Web Service" type). Default: 8000
    MAX_MB      - max file size (MB) to upload back to Telegram. Default: 49
"""

import os
import re
import logging
import asyncio
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import yt_dlp
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAX_MB = int(os.environ.get("MAX_MB", "49"))
PORT = int(os.environ.get("PORT", "8000"))

URL_REGEX = re.compile(r"https?://\S+")


# ---------- tiny health check server (so Koyeb's Web Service sees an open port) ----------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return  # silence default logging


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


# ---------- bot handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salaan! 👋\n\n"
        "Ii soo dir link video ah (YouTube, TikTok, Facebook, Instagram, Twitter/X iwm) "
        "waanan kuu soo dejin doonaa.\n\n"
        "Tusaale: https://www.tiktok.com/@user/video/xxxxxxx"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)

    if not match:
        await update.message.reply_text("Fadlan ii dir link (URL) video ah oo sax ah.")
        return

    url = match.group(0)
    chat_id = update.effective_chat.id

    status_msg = await update.message.reply_text("⏳ Waan soo dejinayaa video-ga, sug wax yar...")
    await context.bot.send_chat_actio
