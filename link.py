import os
import re
import bleach
import yt_dlp
import requests
from flask import Flask, request, jsonify, send_file, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from urllib.parse import urlparse

app = Flask(__name__, template_folder='templates', static_folder='static')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day", "10 per minute"],
    storage_uri="memory://"
)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ── Allowed domains (whitelist) ──────────────────────
ALLOWED_DOMAINS = [
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "twitch.tv", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "soundcloud.com", "facebook.com", "reddit.com"
]

# ── Blocked file extensions ──────────────────────────
BLOCKED_EXTENSIONS = [".exe", ".bat", ".sh", ".php", ".js", ".py"]

def is_safe_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Only http/https links are allowed."
        domain = parsed.netloc.lower().replace("www.", "")
        if not any(allowed in domain for allowed in ALLOWED_DOMAINS):
            return False, f"Domain not supported. Allowed: {', '.join(ALLOWED_DOMAINS)}"
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS):
            return False, "This file type is not allowed."
        return True, "OK"
    except Exception:
        return False, "Invalid URL."

def sanitize_filename(filename):
    filename = re.sub(r'[^\w\s\-.]', '', filename)
    filename = filename[:100]
    return filename or "download"

def download_with_ytdlp(url, quality="best"):
    format_map = {
        "best":  "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "mp3":   "bestaudio/best",
    }

    selected_format = format_map.get(quality, "bestvideo+bestaudio/best")

    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
        "format": selected_format,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if quality == "mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if quality == "mp3":
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename

def download_file(url):
    parsed = urlparse(url)
    filename = sanitize_filename(os.path.basename(parsed.path)) or "file"
    save_path = os.path.join(DOWNLOAD_FOLDER, filename)
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    content_length = int(response.headers.get("content-length", 0))
    if content_length > 500 * 1024 * 1024:
        raise ValueError("File too large (max 500MB).")

    with open(save_path, "wb") as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded > 500 * 1024 * 1024:
                raise ValueError("File too large (max 500MB).")
    return save_path

MEDIA_DOMAINS = [
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "twitch.tv", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "soundcloud.com"
]

def is_media_site(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in MEDIA_DOMAINS)

# ── THIS WAS MISSING — Home route ────────────────────
@app.route("/")
def home():
    return render_template("index.html")

# ── Download route ────────────────────────────────────
@app.route("/download", methods=["POST"])
@limiter.limit("10 per minute")
def download():
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "No URL provided."}), 400

    url = bleach.clean(data.get("url", "").strip())
    quality = bleach.clean(data.get("quality", "best").strip())

    allowed_qualities = ["best", "1080p", "720p", "480p", "360p", "mp3"]
    if quality not in allowed_qualities:
        quality = "best"

    safe, message = is_safe_url(url)
    if not safe:
        return jsonify({"error": message}), 400

    try:
        if is_media_site(url):
            filepath = download_with_ytdlp(url, quality)
        else:
            filepath = download_file(url)
        return send_file(filepath, as_attachment=True)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Download failed. Please try another link."}), 500

# ── Security headers ──────────────────────────────────
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';"
    return response

if __name__ == "__main__":
    app.run(debug=False)