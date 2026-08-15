import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse

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

# Telegram bot upload safety limit
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
# HELPERS
# =========================================================

def get_hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_tiktok(url: str) -> bool:
    host = get_hostname(url)

    return (
        host in TIKTOK_HOSTS
        or host.endswith(".tiktok.com")
    )


def extract_url(text: str):
    match = URL_REGEX.search(text)

    if not match:
        return None

    return match.group(0).rstrip(
        ".,!?)]}>'\""
    )


# =========================================================
# RESOLVE SHORT LINKS
# =========================================================

def resolve_url(url: str) -> str:

    try:
        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; "
                "Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0 "
                "Mobile Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

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

    except Exception as e:
        print(
            "Short-link resolution failed:",
            repr(e)
        )

    return url


# =========================================================
# YT-DLP DOWNLOAD
# =========================================================

def download_media(
    url: str,
    output_dir: str
):

    output_template = os.path.join(
        output_dir,
        "%(title).70s-%(id)s.%(ext)s"
    )

    options = {

        # Best quality while preferring MP4.
        "format": (
            "bv*[ext=mp4]+ba[ext=m4a]/"
            "b[ext=mp4]/"
            "bv*+ba/"
            "b"
        ),

        "outtmpl": output_template,

        "merge_output_format": "mp4",

        # IMPORTANT:
        # Never download playlists.
        "noplaylist": True,

        # Retry.
        "retries": 5,
        "fragment_retries": 5,

        # Timeout.
        "socket_timeout": 30,

        # Network.
        "http_chunk_size": 10485760,

        # Filename.
        "restrictfilenames": True,

        # Cleaner.
        "quiet": True,
        "no_warnings": True,

        # Don't download unnecessary things.
        "writethumbnail": False,
        "writesubtitles": False,
        "writeautomaticsub": False,

        # Keep temporary files inside temp directory.
        "nopart": False,

        # Avoid playlists.
        "extract_flat": False,
    }

    # =====================================================
    # TIKTOK SETTINGS
    # =====================================================

    if is_tiktok(url):

        options["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; "
                "Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0 "
                "Mobile Safari/537.36"
            ),
            "Referer": "https://www.tiktok.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # yt-dlp supports TikTok extractor arguments
        # such as app_name, app_version and API hostname.
        options["extractor_args"] = {
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
    # CURL_CFFI IF INSTALLED
    # =====================================================

    try:
        import curl_cffi

        options["impersonate"] = "chrome"

        print(
            "curl_cffi detected:",
            getattr(
                curl_cffi,
                "__version__",
                "installed"
            )
        )

    except Exception:
        print(
            "curl_cffi not installed; "
            "using normal HTTP client."
        )

    # =====================================================
    # DOWNLOAD
    # =====================================================

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        if not info:
            raise RuntimeError(
                "yt-dlp returned no information."
            )

        prepared = Path(
            ydl.prepare_filename(info)
        )

        candidates = [
            prepared,
            prepared.with_suffix(".mp4"),
            prepared.with_suffix(".mkv"),
            prepared.with_suffix(".webm"),
            prepared.with_suffix(".mov"),
            prepared.with_suffix(".m4v"),
        ]

        for candidate in candidates:

            if candidate.exists():

                return (
                    str(candidate),
                    info
                )

        # Fallback search.
        files = [
            p
            for p in Path(output_dir).iterdir()
            if p.is_file()
        ]

        if files:

            largest = max(
                files,
                key=lambda p: p.stat().st_size
            )

            return (
                str(largest),
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
        "🎬 Ii soo dir video link.\n\n"
        "Waxaan taageeraa websites badan "
        "oo yt-dlp leeyahay extractor.\n\n"
        "📌 Tusaale:\n"
        "TikTok\n"
        "YouTube\n"
        "Instagram\n"
        "Facebook\n"
        "X/Twitter\n"
        "iyo kuwo kale.\n\n"
        "🔗 Link-ga soo dir..."
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
        "1️⃣ Copy video link\n"
        "2️⃣ Bot-ka ugu soo dir\n"
        "3️⃣ Sug download-ka\n"
        "4️⃣ Video-ga Telegram ayuu kuu soo dirayaa 🎬\n\n"
        "⚠️ Private/login/blocked videos "
        "lama soo dejin karo haddii website-ku "
        "u baahan yahay authentication."
    )


# =========================================================
# /ABOUT
# =========================================================

async def about(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 Multi-Site Downloader\n\n"
        "Python + Telegram Bot API + yt-dlp\n\n"
        "🎬 Link → Download → Telegram"
    )


# =========================================================
# HANDLE VIDEO LINK
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
        "🔎 Link-ga waan hubinayaa..."
    )

    temp_dir = tempfile.mkdtemp(
        prefix="video_bot_"
    )

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
            "Original:",
            original_url
        )

        print(
            "Resolved:",
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

        if not os.path.exists(video_path):

            raise FileNotFoundError(
                "Video file does not exist."
            )

        # =================================================
        # SIZE
        # =================================================

        size = os.path.getsize(
            video_path
        )

        if size > MAX_FILE_SIZE:

            size_mb = size / (
                1024 * 1024
            )

            await status.edit_text(
                "❌ Video-ga aad buu u weyn yahay.\n\n"
                f"📦 Size: {size_mb:.1f} MB\n"
                "📌 Limit-ka bot-kan: ~49 MB."
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

        await update.message.chat.send_action(
            ChatAction.UPLOAD_VIDEO
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
            ".mkv"
        }

        if extension in video_extensions:

            try:

                with open(
                    video_path,
                    "rb"
                ) as media:

                    await update.message.reply_video(
                        video=media,
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=180,
                        write_timeout=180,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

            except Exception as upload_error:

                print(
                    "Video upload error:",
                    repr(upload_error)
                )

                # Fallback document upload.
                with open(
                    video_path,
                    "rb"
                ) as media:

                    await update.message.reply_document(
                        document=media,
                        caption=caption,
                        read_timeout=180,
                        write_timeout=180,
                        connect_timeout=30,
                        pool_timeout=30,
                    )

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
                    read_timeout=180,
                    write_timeout=180,
                    connect_timeout=30,
                    pool_timeout=30,
                )

        try:
            await status.delete()
        except Exception:
            pass

    # =====================================================
    # DOWNLOAD ERROR
    # =====================================================

    except yt_dlp.utils.DownloadError as error:

        error_text = str(error)

        print(
            "YT-DLP ERROR:",
            error_text
        )

        lower = error_text.lower()

        if is_tiktok(resolved_url if "resolved_url" in locals() else original_url):

            message = (
                "❌ TikTok download-ku wuu fashilmay.\n\n"
                "TikTok ayaa mararka qaar beddela "
                "habka video-ga loo helo, waxaana jira "
                "xaalado ay yt-dlp TikTok uga fashilanto "
                "xitaa iyadoo version cusub la isticmaalayo.\n\n"
                "🔄 Isku day link-ga mar kale."
            )

        elif "unsupported url" in lower:

            message = (
                "❌ Website-kan yt-dlp ma taageero.\n\n"
                "🔗 Isku day link website kale."
            )

        elif (
            "login" in lower
            or "sign in" in lower
            or "authentication" in lower
        ):

            message = (
                "🔐 Video-ga wuxuu u baahan yahay login.\n\n"
                "Bot-ku ma isticmaali karo account-kaaga "
                "la'aanteed cookies/authentication."
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
                "Isku day link kale ama mar dambe."
            )

        elif (
            "too large" in lower
            or "filesize" in lower
        ):

            message = (
                "📦 Video-ga aad buu u weyn yahay.\n\n"
                "Fadlan isticmaal video ka yar 49 MB."
            )

        else:

            message = (
                "❌ Video-ga lama soo dejin karin.\n\n"
                "Sababta saxda ah:\n\n"
                f"{error_text[:900]}"
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
            f"Error: {str(error)[:700]}"
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
            "BOT_TOKEN lama helin.\n"
            "Ku dar BOT_TOKEN environment variable."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

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
        "================================"
    )

    print(
        "🤖 VIDEO DOWNLOADER BOT"
    )

    print(
        "✅ Bot is running..."
    )

    print(
        "================================"
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
