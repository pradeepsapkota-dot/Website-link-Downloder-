import re
import bleach
import yt_dlp
import requests
from flask import Flask, request, jsonify, render_template, redirect
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

ALLOWED_DOMAINS = [
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "twitch.tv", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "soundcloud.com", "facebook.com", "reddit.com"
]

BLOCKED_EXTENSIONS = [".exe", ".bat", ".sh", ".php", ".js", ".py"]
ALLOWED_DIRECT_EXTENSIONS = [".mp4", ".mp3",
                             ".mkv", ".avi", ".mov", ".wav", ".webm"]


def is_safe_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Only http/https links are allowed."

        path = parsed.path.lower()

        # Block dangerous extensions
        if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS):
            return False, "This file type is not allowed."

        domain = parsed.netloc.lower().replace("www.", "")

        # Allow direct media file links from any domain
        if any(path.endswith(ext) for ext in ALLOWED_DIRECT_EXTENSIONS):
            return True, "OK"

        # Otherwise must be whitelisted domain
        if not any(allowed in domain for allowed in ALLOWED_DOMAINS):
            return False, f"Domain not supported. Allowed: {', '.join(ALLOWED_DOMAINS)}"

        return True, "OK"
    except Exception:
        return False, "Invalid URL."


MEDIA_DOMAINS = [
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "twitch.tv", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "soundcloud.com"
]


def is_media_site(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in MEDIA_DOMAINS)


def get_direct_url(url, quality="best"):
    format_map = {
        "best":  "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "mp3":   "bestaudio/best",
    }

    ydl_opts = {
        "format": format_map.get(quality, "best"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        # Add these:
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # Return the direct stream URL
        return info.get("url") or info["requested_formats"][0]["url"]


@app.route("/")
def home():
    return render_template("index.html")


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
            direct_url = get_direct_url(url, quality)
            # Return the direct URL to the frontend
            # Browser downloads it directly from the source
            return jsonify({"download_url": direct_url})
        else:
            # For non-media sites, just return the URL as-is
            return jsonify({"download_url": url})
    except Exception as e:
        return jsonify({"error": "Could not extract download link. Try another URL."}), 500


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
