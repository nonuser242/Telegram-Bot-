import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests
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

# Telegram Bot API safety limit
MAX_FILE_SIZE = 49 * 1024 * 1024

URL_REGEX = re.compile(
    r"https?://[^\s]+",
    re.IGNORECASE
)

TIKTOK_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}


# =========================================================
# URL HELPERS
# =========================================================

def extract_url(text: str):
    match = URL_REGEX.search(text)

    if not match:
        return None

    return match.group(0).rstrip(
        ".,!?)]}>'\""
    )


def get_hostname(url: str):
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_tiktok(url: str):
    host = get_hostname(url)

    return (
        host in TIKTOK_HOSTS
        or host.endswith(".tiktok.com")
    )


# =========================================================
# RESOLVE SHORT URL
# =========================================================

def resolve_url(url: str):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            allow_redirects=True,
            timeout=20,
            stream=True,
        )

        final_url = response.url

        response.close()

        if final_url:
            return final_url

    except Exception as error:
        print(
            "URL resolve error:",
            repr(error)
        )

    return url


# =========================================================
# DOWNLOAD
# =========================================================

def download_media(
    url: str,
    output_dir: str
):

    output_template = os.path.join(
        output_dir,
        "%(title).80s-%(id)s.%(ext)s"
    )

    ydl_opts = {
        # Best available quality.
        # Prefer MP4 when possible.
        "format": (
            "bestvideo[ext=mp4]+"
            "bestaudio[ext=m4a]/"
            "best[ext=mp4]/"
            "bestvideo+bestaudio/"
            "best"
        ),

        "outtmpl": output_template,

        # Merge audio + video.
        "merge_output_format": "mp4",

        # Don't download playlists.
        "noplaylist": True,

        # Retries.
        "retries": 5,
        "fragment_retries": 5,

        # Network timeout.
        "socket_timeout": 30,

        # Better filenames.
        "restrictfilenames": True,

        # Cleaner logs.
        "quiet": True,
        "no_warnings": True,

        # No unnecessary files.
        "writethumbnail": False,
        "writesubtitles": False,
        "writeautomaticsub": False,

        # Continue interrupted downloads.
        "continuedl": True,

        # Don't download files known to be larger.
        "max_filesize": MAX_FILE_SIZE,
    }

    # =====================================================
    # TIKTOK
    # =====================================================

    if is_tiktok(url):

        ydl_opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Mobile Safari/537.36"
            ),
            "Referer": "https://www.tiktok.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

        ydl_opts["extractor_args"] = {
            "tiktok": {
                "api_hostname": [
                    "api16-normal-c-useast1a.tiktokv.com"
                ],
                "app_name": [
                    "musical_ly"
                ],
                "app_version": [
                    "35.1.3"
                ],
                "manifest_app_version": [
                    "2023501030"
                ],
                "aid": [
                    "0"
                ],
            }
        }

    # =====================================================
    # DOWNLOAD WITH YT-DLP
    # =====================================================

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        if not info:
            raise RuntimeError(
                "yt-dlp returned no information."
            )

        prepared_file = Path(
            ydl.prepare_filename(info)
        )

        candidates = [
            prepared_file,
            prepared_file.with_suffix(".mp4"),
            prepared_file.with_suffix(".mkv"),
            prepared_file.with_suffix(".webm"),
            prepared_file.with_suffix(".mov"),
            prepared_file.with_suffix(".m4v"),
        ]

        for file_path in candidates:

            if file_path.exists():

                return (
                    str(file_path),
                    info
                )

        # Fallback: search directory.
        files = [
            file
            for file in Path(output_dir).iterdir()
            if file.is_file()
        ]

        if files:

            largest_file = max(
                files,
                key=lambda file: file.stat().st_size
            )

            return (
                str(largest_file),
                info
            )

        raise FileNotFoundError(
            "Downloaded file was not found."
        )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Soo dhawoow!\n\n"
        "🎬 Waxaan ahay Multi-Site Video Downloader.\n\n"
        "🔗 Ii soo dir video link.\n\n"
        "Waxaan isku dayayaa websites badan "
        "oo yt-dlp taageero.\n\n"
        "Tusaale:\n"
        "• TikTok\n"
        "• YouTube\n"
        "• Instagram\n"
        "• Facebook\n"
        "• X/Twitter\n"
        "• Websites kale\n\n"
        "⬇️ Link-ga soo dir..."
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
        "1️⃣ Copy garee video link.\n"
        "2️⃣ Bot-ka ugu soo dir.\n"
        "3️⃣ Sug download-ka.\n"
        "4️⃣ Bot-ku Telegram ayuu kuu soo dirayaa.\n\n"
        "⚠️ Private/login/blocked videos "
        "waxaa laga yaabaa inaan la soo dejin karin."
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
        "🔗 Link → Download → Telegram"
    )


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

    original_url = extract_url(text)

    if not original_url:

        await update.message.reply_text(
            "❌ Link ma helin.\n\n"
            "Ii soo dir link bilaabanaya "
            "http:// ama https://"
        )

        return

    status = await update.message.reply_text(
        "🔎 Link-ga waan hubinayaa...\n"
        "⏳ Fadlan sug."
    )

    temp_dir = tempfile.mkdtemp(
        prefix="telegram_video_"
    )

    resolved_url = original_url

    try:

        # =================================================
        # RESOLVE SHORT LINK
        # =================================================

        await status.edit_text(
            "🔗 Link-ga waan furayaa..."
        )

        resolved_url = await asyncio.to_thread(
            resolve_url,
            original_url
        )

        print(
            "Original URL:",
            original_url
        )

        print(
            "Resolved URL:",
            resolved_url
        )

        # =================================================
        # DOWNLOAD
        # =================================================

        await status.edit_text(
            "⬇️ Video-ga waan soo dejinayaa...\n\n"
            "⏳ Fadlan sug."
        )

        await update.message.chat.send_action(
            ChatAction.TYPING
        )

        video_path, info = await asyncio.to_thread(
            download_media,
            resolved_url,
            temp_dir
        )

        # =================================================
        # CHECK FILE
        # =================================================

        if not os.path.exists(video_path):

            raise FileNotFoundError(
                "Downloaded video does not exist."
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
                "📌 Bot-kan wuxuu aqbalayaa "
                "qiyaastii 49 MB."
            )

            return

        # =================================================
        # TITLE
        # =================================================

        title = info.get(
            "title",
            "Video"
        )

        caption = (
            f"🎬 {title[:700]}"
        )

        # =================================================
        # UPLOAD
        # =================================================

        await status.edit_text(
            "✅ Download waa dhammaaday!\n\n"
            "📤 Telegram ayaan kuu dirayaa..."
        )

        extension = (
            Path(video_path)
            .suffix
            .lower()
        )

        video_extensions = {
            ".mp4",
            ".m4v",
            ".mov",
            ".webm",
            ".mkv",
            ".avi"
        }

        # =================================================
        # SEND VIDEO
        # =================================================

        if extension in video_extensions:

            await update.message.chat.send_action(
                ChatAction.UPLOAD_VIDEO
            )

            try:

                with open(
                    video_path,
                    "rb"
                ) as video:

                    await update.message.reply_video(
                        video=video,
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=180,
                        write_timeout=180,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

            except Exception as upload_error:

                print(
                    "Video upload failed:",
                    repr(upload_error)
                )

                # Fallback to document.
                with open(
                    video_path,
                    "rb"
                ) as video:

                    await update.message.reply_document(
                        document=video,
                        caption=caption,
                        read_timeout=180,
                        write_timeout=180,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

        # =================================================
        # SEND AS DOCUMENT
        # =================================================

        else:

            await update.message.chat.send_action(
                ChatAction.UPLOAD_DOCUMENT
            )

            with open(
                video_path,
                "rb"
            ) as video:

                await update.message.reply_document(
                    document=video,
                    caption=caption,
                    read_timeout=180,
                    write_timeout=180,
                    connect_timeout=30,
                    pool_timeout=30,
                )

        # Delete status.
        try:
            await status.delete()
        except Exception:
            pass

    # =====================================================
    # YT-DLP ERROR
    # =====================================================

    except yt_dlp.utils.DownloadError as error:

        error_text = str(error)

        print(
            "YT-DLP ERROR:",
            error_text
        )

        lower = error_text.lower()

        # TikTok-specific message.
        if is_tiktok(resolved_url):

            if (
                "unsupported" in lower
                or "extract" in lower
                or "video data" in lower
                or "403" in lower
                or "forbidden" in lower
            ):

                message = (
                    "❌ TikTok video-ga lama soo dejin karin.\n\n"
                    "TikTok ayaa xannibi kara request-ka "
                    "ama beddeli kara habka video-ga loo helo.\n\n"
                    "🔄 Isku day link-ga mar kale."
                )

            else:

                message = (
                    "❌ TikTok download-ku wuu fashilmay.\n\n"
                    f"Error:\n{error_text[:800]}"
                )

        elif "unsupported url" in lower:

            message = (
                "❌ Website-kan lama taageero.\n\n"
                "🔗 Isku day link website kale."
            )

        elif (
            "login" in lower
            or "sign in" in lower
            or "authentication" in lower
        ):

            message = (
                "🔐 Video-ga wuxuu u baahan yahay login.\n\n"
                "Bot-ku ma geli karo account gaar ah."
            )

        elif (
            "private" in lower
            or "unavailable" in lower
            or "not available" in lower
        ):

            message = (
                "❌ Video-ga lama heli karo.\n\n"
                "Waxaa laga yaabaa inuu private yahay "
                "ama la tirtiray."
            )

        elif (
            "403" in lower
            or "forbidden" in lower
            or "blocked" in lower
        ):

            message = (
                "🚫 Website-ku wuxuu diiday request-ka.\n\n"
                "Isku day link kale."
            )

        elif (
            "too large" in lower
            or "filesize" in lower
            or "file size" in lower
        ):

            message = (
                "📦 Video-ga aad buu u weyn yahay.\n\n"
                "Fadlan isticmaal video ka yar 49 MB."
            )

        else:

            message = (
                "❌ Video-ga lama soo dejin karin.\n\n"
                f"Error:\n{error_text[:1000]}"
            )

        await status.edit_text(
            message
        )

    # =====================================================
    # GENERAL ERROR
    # =====================================================

    except Exception as error:

        print(
            "GENERAL ERROR:",
            repr(error)
        )

        await status.edit_text(
            "❌ Wax ayaa qaldamay.\n\n"
            f"Error:\n{str(error)[:1000]}"
        )

    # =====================================================
    # CLEAN TEMP FILES
    # =====================================================

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


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
            "BOT_TOKEN lama helin.\n\n"
            "Ku dar BOT_TOKEN environment variable."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
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

    # Links / text
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_link
        )
    )

    # Errors
    app.add_error_handler(
        error_handler
    )

    print(
        "===================================="
    )
    print(
        "🤖 MULTI-SITE TELEGRAM DOWNLOADER"
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
# START BOT
# =========================================================

if __name__ == "__main__":
    main()
