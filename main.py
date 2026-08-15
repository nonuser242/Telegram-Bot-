import os
import re
import asyncio
import tempfile
from pathlib import Path

import yt_dlp
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Telegram Bot API upload limit is commonly around 50 MB.
# Keep a little margin so the upload has a better chance of succeeding.
MAX_FILE_SIZE = 49 * 1024 * 1024

URL_REGEX = re.compile(
    r"^https?://",
    re.IGNORECASE
)


# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Soo dhawoow!\n\n"
        "🎬 Ii soo dir link video ah.\n"
        "Waxaan isku dayayaa inaan soo dejiyo kadibna Telegram-ka kuugu soo diro.\n\n"
        "📌 Tusaale:\n"
        "https://example.com/video\n\n"
        "ℹ️ /help - Caawimaad"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Sida loo isticmaalo:\n\n"
        "1️⃣ Copy garee link-ga video-ga\n"
        "2️⃣ Halkan bot-ka ugu soo dir\n"
        "3️⃣ Sug inta uu download-ku dhammaanayo\n"
        "4️⃣ Bot-ku video-ga ayuu kuu soo celinayaa 🎬\n\n"
        "⚠️ Link-ga waa inuu noqdaa http ama https."
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Video Bot\n\n"
        "Waxaa lagu dhisay Python + python-telegram-bot + yt-dlp."
    )


# =========================
# DOWNLOAD FUNCTION
# =========================

def download_video(url: str, output_dir: str):
    """
    Runs yt-dlp synchronously.
    This function is executed in a background thread.
    """

    output_template = os.path.join(
        output_dir,
        "%(title).80s-%(id)s.%(ext)s"
    )

    ydl_opts = {
        # Prefer MP4 when available.
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/"
            "best"
        ),

        "outtmpl": output_template,

        # Merge video/audio into MP4 when ffmpeg is installed.
        "merge_output_format": "mp4",

        # Do not download playlists.
        "noplaylist": True,

        # Avoid keeping unnecessary files.
        "writethumbnail": False,
        "writesubtitles": False,

        # Quiet output.
        "quiet": True,
        "no_warnings": True,

        # Respect websites' normal restrictions.
        "restrictfilenames": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        downloaded_file = ydl.prepare_filename(info)

        # If ffmpeg merged the file into mp4, prepare_filename()
        # may still point to the original extension.
        possible_files = [
            Path(downloaded_file),
            Path(os.path.splitext(downloaded_file)[0] + ".mp4"),
            Path(os.path.splitext(downloaded_file)[0] + ".mkv"),
            Path(os.path.splitext(downloaded_file)[0] + ".webm"),
        ]

        for file_path in possible_files:
            if file_path.exists():
                return str(file_path)

        # Last-resort search.
        files = list(Path(output_dir).glob("*"))

        if files:
            return str(files[0])

        raise FileNotFoundError("Downloaded video file was not found.")


# =========================
# HANDLE URL
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    # Check URL.
    if not URL_REGEX.match(url):
        await update.message.reply_text(
            "❌ Taasi uma muuqato link sax ah.\n\n"
            "Fadlan ii soo dir link bilaabanaya:\n"
            "http:// ama https://"
        )
        return

    status = await update.message.reply_text(
        "⏳ Video-ga waan soo dejinayaa...\n"
        "Fadlan sug."
    )

    await update.message.chat.send_action(
        ChatAction.TYPING
    )

    temp_dir = tempfile.mkdtemp(prefix="telegram_video_")

    try:
        # Run yt-dlp outside the Telegram event loop.
        video_path = await asyncio.to_thread(
            download_video,
            url,
            temp_dir
        )

        # Check file exists.
        if not os.path.exists(video_path):
            raise FileNotFoundError("Video file not found.")

        file_size = os.path.getsize(video_path)

        # Check size before uploading.
        if file_size > MAX_FILE_SIZE:
            await status.edit_text(
                "❌ Video-ga aad buu u weyn yahay.\n\n"
                f"📦 Size: {file_size / (1024 * 1024):.1f} MB\n"
                "📌 Fadlan isticmaal video ka yar 49 MB."
            )
            return

        await status.edit_text(
            "✅ Download waa dhammaaday!\n"
            "📤 Telegram ayaan u dirayaa..."
        )

        await update.message.chat.send_action(
            ChatAction.UPLOAD_VIDEO
        )

        # Send video.
        with open(video_path, "rb") as video_file:

            await update.message.reply_video(
                video=video_file,
                supports_streaming=True,
                caption="🎬 Video-gaaga waa kan!"
            )

        # Remove status message.
        try:
            await status.delete()
        except Exception:
            pass

    except yt_dlp.utils.DownloadError as e:

        print("yt-dlp error:", e)

        await status.edit_text(
            "❌ Video-ga lama soo dejin karin.\n\n"
            "Sababaha suuragalka ah:\n"
            "• Link-ga ma shaqeynayo\n"
            "• Video-ga lama heli karo\n"
            "• Website-ku ma oggola download\n"
            "• Video-ga wuxuu u baahan yahay login\n"
            "• Website-ku wuxuu leeyahay restriction"
        )

    except Exception as e:

        print("ERROR:", repr(e))

        await status.edit_text(
            "❌ Wax ayaa qaldamay.\n\n"
            "Fadlan hubi link-ga kadib isku day mar kale."
        )

    finally:
        # Delete temporary files.
        try:
            for file in Path(temp_dir).glob("*"):
                try:
                    file.unlink()
                except Exception:
                    pass

            try:
                Path(temp_dir).rmdir()
            except Exception:
                pass

        except Exception:
            pass


# =========================
# ERROR HANDLER
# =========================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print(
        "Telegram error:",
        repr(context.error)
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands.
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("about", about)
    )

    # Messages containing URLs.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    # Error handler.
    app.add_error_handler(error_handler)

    print("🤖 Telegram Video Bot is running...")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
