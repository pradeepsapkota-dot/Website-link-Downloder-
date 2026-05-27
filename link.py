import bleach
import requests
from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__, template_folder='templates', static_folder='static')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day", "10 per minute"],
    storage_uri="memory://"
)


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

    # Map quality to cobalt format
    quality_map = {
        "best": "1080",
        "1080p": "1080",
        "720p": "720",
        "480p": "480",
        "360p": "360",
        "mp3": "audio"
    }

    is_audio = quality == "mp3"
    video_quality = quality_map.get(quality, "1080")

    try:
        response = requests.post(
            "https://api.cobalt.tools/",
            json={
                "url": url,
                "videoQuality": video_quality,
                "downloadMode": "audio" if is_audio else "auto",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout=15
        )

        result = response.json()

        # Cobalt returns either 'url' or 'picker' (multiple streams)
        if result.get("url"):
            return jsonify({"download_url": result["url"]})
        elif result.get("picker"):
            # Return first option from picker
            return jsonify({"download_url": result["picker"][0]["url"]})
        else:
            return jsonify({"error": result.get("error", {}).get("code", "Could not extract link.")}), 500

    except Exception as e:
        return jsonify({"error": "Something went wrong. Try again."}), 500


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
