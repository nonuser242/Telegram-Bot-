import os
import re
import shutil
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


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Telegram upload limit is currently 50 MB.
# We keep a small safety margin.
MAX_FILE_SIZE = 49 * 1024 * 1024

URL_PATTERN = re.compile(
    r"https?://[^\s]+",
    re.IGNORECASE
)


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Soo dhawoow!\n\n"
        "🎬 Waxaan ahay Video Downloader Bot.\n\n"
        "🔗 Ii soo dir link video ah, tusaale:\n"
        "TikTok\n"
        "YouTube\n"
        "Instagram\n"
        "Facebook\n"
        "X/Twitter\n"
        "iyo websites kale oo yt-dlp taageero.\n\n"
        "⏳ Link-ga soo dir oo sug..."
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📖 Sida loo isticmaalo:\n\n"
        "1️⃣ Copy garee video link\n"
        "2️⃣ Halkan bot-ka ugu soo dir\n"
        "3️⃣ Bot-ku wuxuu isku dayayaa inuu download-gareeyo\n"
        "4️⃣ Kadib Telegram ayuu kuu soo dirayaa 🎬\n\n"
        "✅ Links badan ayaa la taageeraa.\n"
        "⚠️ Video aad u weyn ama website xannibay download "
        "lama soo dejin karo."
    )


# =========================================================
# /ABOUT
# =========================================================

async def about(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 Multi-Site Video Downloader\n\n"
        "⚙️ Python\n"
        "⚙️ yt-dlp\n"
        "⚙️ python-telegram-bot\n\n"
        "🎬 Download → Telegram"
    )


# =========================================================
# FIND URL
# =========================================================

def extract_url(text: str):

    match = URL_PATTERN.search(text)

    if not match:
        return None

    return match.group(0).rstrip(".,!?)]}")


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

def download_media(url: str, output_dir: str):

    output_template = os.path.join(
        output_dir,
        "%(title).80s-%(id)s.%(ext)s"
    )

    ydl_opts = {

        # Prefer MP4.
        # If video/audio are separate, ffmpeg will merge them.
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/"
            "bestvideo+bestaudio/"
            "best"
        ),

        "outtmpl": output_template,

        # Merge when possible.
        "merge_output_format": "mp4",

        # Never download playlists.
        "noplaylist": True,

        # Avoid extra files.
        "writethumbnail": False,
        "writesubtitles": False,
        "writeautomaticsub": False,

        # Cleaner logs.
        "quiet": True,
        "no_warnings": True,

        # Better filenames.
        "restrictfilenames": True,

        # Continue when possible.
        "continuedl": True,

        # Don't download huge files when size is known.
        "max_filesize": MAX_FILE_SIZE,

        # Network retries.
        "retries": 3,
        "fragment_retries": 3,

        # Timeout.
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        if not info:
            raise RuntimeError(
                "No media information returned."
            )

        prepared = Path(
            ydl.prepare_filename(info)
        )

        # Possible output files after FFmpeg merge.
        candidates = [
            prepared,
            prepared.with_suffix(".mp4"),
            prepared.with_suffix(".mkv"),
            prepared.with_suffix(".webm"),
            prepared.with_suffix(".mov"),
            prepared.with_suffix(".avi"),
        ]

        for file_path in candidates:

            if file_path.exists():
                return str(file_path), info

        # Search the temporary directory as fallback.
        files = [
            p for p in Path(output_dir).iterdir()
            if p.is_file()
        ]

        if not files:
            raise FileNotFoundError(
                "Downloaded file was not found."
            )

        # Pick the largest file.
        largest = max(
            files,
            key=lambda p: p.stat().st_size
        )

        return str(largest), info


# =========================================================
# HANDLE LINK
# =========================================================

async def handle_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text or ""

    url = extract_url(text)

    if not url:

        await update.message.reply_text(
            "❌ Link ma helin.\n\n"
            "Fadlan ii soo dir link bilaabanaya "
            "http:// ama https://"
        )

        return

    status = await update.message.reply_text(
        "🔎 Link-ga waan hubinayaa...\n"
        "⏳ Fadlan sug."
    )

    temp_dir = tempfile.mkdtemp(
        prefix="telegram_downloader_"
    )

    try:

        await update.message.chat.send_action(
            ChatAction.TYPING
        )

        # Download in background thread so the bot
        # can continue handling other Telegram events.
        video_path, info = await asyncio.to_thread(
            download_media,
            url,
            temp_dir
        )

        if not os.path.exists(video_path):

            raise FileNotFoundError(
                "Downloaded media does not exist."
            )

        file_size = os.path.getsize(
            video_path
        )

        # =================================================
        # SIZE CHECK
        # =================================================

        if file_size > MAX_FILE_SIZE:

            size_mb = file_size / (
                1024 * 1024
            )

            await status.edit_text(
                "❌ Video-ga aad buu u weyn yahay.\n\n"
                f"📦 Size: {size_mb:.1f} MB\n"
                "📌 Limit-ka bot-kan: qiyaastii 49 MB."
            )

            return

        # =================================================
        # TITLE
        # =================================================

        title = info.get(
            "title",
            "Video"
        )

        # Telegram caption max is limited, so keep it short.
        caption = (
            f"🎬 {title[:700]}\n\n"
            "🤖 Downloaded by Video Bot"
        )

        await status.edit_text(
            "✅ Download waa dhammaaday!\n\n"
            "📤 Telegram ayaan kuu soo dirayaa..."
        )

        await update.message.chat.send_action(
            ChatAction.UPLOAD_VIDEO
        )

        suffix = Path(
            video_path
        ).suffix.lower()

        # =================================================
        # SEND AS VIDEO
        # =================================================

        video_extensions = {
            ".mp4",
            ".m4v",
            ".mov",
            ".webm"
        }

        if suffix in video_extensions:

            try:

                with open(
                    video_path,
                    "rb"
                ) as media:

                    await update.message.reply_video(
                        video=media,
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

            except Exception as video_error:

                print(
                    "Video upload failed:",
                    repr(video_error)
                )

                # Fallback: send as document.
                with open(
                    video_path,
                    "rb"
                ) as media:

                    await update.message.reply_document(
                        document=media,
                        caption=caption,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

        # =================================================
        # SEND OTHER MEDIA AS DOCUMENT
        # =================================================

        else:

            await update.message.chat.send_action(
                ChatAction.UPLOAD_DOCUMENT
            )

            with open(
                video_path,
                "rb"
            ) as media:

                await update.message.reply_document(
                    document=media,
                    caption=caption,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30,
                    pool_timeout=30,
                )

        # Remove status message.
        try:
            await status.delete()
        except Exception:
            pass

    # =====================================================
    # YT-DLP ERROR
    # =====================================================

    except yt_dlp.utils.DownloadError as error:

        print(
            "yt-dlp ERROR:",
            repr(error)
        )

        error_text = str(error).lower()

        if (
            "unsupported url" in error_text
            or "no suitable extractor" in error_text
        ):

            message = (
                "❌ Website-kan/link-kan lama taageerin.\n\n"
                "💡 Isku day link kale."
            )

        elif (
            "login" in error_text
            or "sign in" in error_text
            or "authentication" in error_text
        ):

            message = (
                "🔐 Video-ga wuxuu u baahan yahay login.\n\n"
                "Bot-ku ma geli karo account-kaaga "
                "si automatic ah."
            )

        elif (
            "private" in error_text
            or "unavailable" in error_text
            or "not available" in error_text
        ):

            message = (
                "❌ Video-ga lama heli karo.\n\n"
                "Waxaa laga yaabaa inuu private yahay "
                "ama la tirtiray."
            )

        elif (
            "403" in error_text
            or "forbidden" in error_text
            or "blocked" in error_text
        ):

            message = (
                "🚫 Website-ku wuxuu xannibay request-ka bot-ka.\n\n"
                "Isku day link kale ama mar dambe."
            )

        elif (
            "filesize" in error_text
            or "too large" in error_text
        ):

            message = (
                "📦 Video-ga aad buu u weyn yahay.\n\n"
                "Fadlan isticmaal video ka yar 49 MB."
            )

        else:

            message = (
                "❌ Download-ku wuu fashilmay.\n\n"
                "Sababtu waxay noqon kartaa:\n"
                "• Link khaldan\n"
                "• Website restriction\n"
                "• Video private ah\n"
                "• Website-ku login ayuu rabaa\n"
                "• Website-ku hadda lama taageero"
            )

        await status.edit_text(
            message
        )

    # =====================================================
    # OTHER ERROR
    # =====================================================

    except Exception as error:

        print(
            "BOT ERROR:",
            repr(error)
        )

        await status.edit_text(
            "❌ Wax ayaa qaldamay.\n\n"
            "Fadlan hubi link-ga oo isku day mar kale."
        )

    # =====================================================
    # CLEANUP
    # =====================================================

    finally:

        try:

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

        except Exception:
            pass


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "Telegram error:",
        repr(context.error)
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN lama helin.\n"
            "Set garee BOT_TOKEN environment variable."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands.
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    app.add_handler(
        CommandHandler(
            "about",
            about
        )
    )

    # Any normal text containing a URL.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_link
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "===================================="
    )

    print(
        "🤖 Multi-Site Telegram Bot"
    )

    print(
        "✅ Bot is running..."
    )

    print(
        "===================================="
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
