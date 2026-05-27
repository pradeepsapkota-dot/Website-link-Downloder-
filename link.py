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
# change if different
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
            f"https://{RAPIDAPI_HOST}/smvd/get/all",  # same host
            params={"url": url},
            headers={
                "x-rapidapi-key": RAPIDAPI_KEY,
                "x-rapidapi-host": RAPIDAPI_HOST
            },
            timeout=15
        )

        result = response.json()

        # Audio requested
        if quality == "mp3":
            audios = result.get("audios", [])
            if audios:
                return jsonify({"download_url": audios[0]["url"]})
            return jsonify({"error": "No audio found."}), 500

        # Video — pick by quality
        videos = result.get("videos", [])
        if not videos:
            return jsonify({"error": "No video found."}), 500

        # Try to match requested quality
        quality_map = {
            "1080p": "1080",
            "720p": "720",
            "480p": "480",
            "360p": "360",
        }
        target = quality_map.get(quality)

        if target:
            for v in videos:
                if target in v.get("resolution", ""):
                    return jsonify({"download_url": v["url"]})

        # Fallback to first (best) video
        return jsonify({"download_url": videos[0]["url"]})

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
