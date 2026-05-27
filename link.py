import bleach
import requests
from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

app = Flask(__name__, template_folder='templates', static_folder='static')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day", "10 per minute"],
    storage_uri="memory://"
)

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
RAPIDAPI_HOST = "social-media-downloader-api13.p.rapidapi.com"

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
    quality = data.get("quality", "best")

    try:
        response = requests.get(
            f"https://{RAPIDAPI_HOST}/download",
            params={"url": url},
            headers={
                "x-rapidapi-key": RAPIDAPI_KEY,
                "x-rapidapi-host": RAPIDAPI_HOST
            },
            timeout=15
        )

        result = response.json()
        videos = result.get("videos", [])
        audios = result.get("audios", [])

        # MP3 request — return best audio
        if quality == "mp3":
            if audios:
                # prefer m4a over webm
                for a in audios:
                    if a.get("ext") == "m4a":
                        return jsonify({"download_url": a["url"]})
                return jsonify({"download_url": audios[0]["url"]})
            return jsonify({"error": "No audio found."}), 500

        # Video request — find format 18 first (combined video+audio mp4)
        for v in videos:
            if v.get("format_id") == "18":
                return jsonify({"download_url": v["url"]})

        # If no format 18, pick by quality (video only, but better than nothing)
        quality_map = {
            "1080p": "1920x1080",
            "720p": "1280x720",
            "480p": "854x480",
            "360p": "640x360",
        }
        target = quality_map.get(quality)
        if target:
            for v in videos:
                if v.get("resolution") == target and v.get("ext") == "mp4":
                    return jsonify({"download_url": v["url"]})

        # Fallback — last mp4
        for v in reversed(videos):
            if v.get("ext") == "mp4":
                return jsonify({"download_url": v["url"]})

        return jsonify({"error": "No video found."}), 500

    except Exception as e:
        return jsonify({"error": "Could not extract download link."}), 500

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