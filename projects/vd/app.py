import os
import re
import sys
import uuid
import shutil
import platform
import subprocess
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, send_file, abort
from werkzeug.utils import secure_filename

APP_ROOT = Path(__file__).resolve().parent
MEDIA_DIR = APP_ROOT / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_UPLOAD_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
YOUTUBE_URL_RE = re.compile(
    r"^https?://(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)[\w\-]+"
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB upload cap

# in-memory registry (fine for a single-process dev/personal-use app)
MEDIA_REGISTRY = {}  # id -> {"path": Path, "duration": float, "filename": str}


def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg is not installed or not on PATH.")
    return path


def ffprobe_duration(path: Path) -> float:
    probe = shutil.which("ffprobe")
    if not probe:
        raise RuntimeError("ffprobe is not installed or not on PATH.")
    out = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def new_id() -> str:
    return uuid.uuid4().hex


@app.route("/")
def index():
    return send_from_directory(APP_ROOT / "templates", "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(APP_ROOT / "static", filename)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename."}), 400

    ext = Path(secure_filename(f.filename)).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    media_id = new_id()
    dest = MEDIA_DIR / f"{media_id}{ext}"
    f.save(dest)

    try:
        duration = ffprobe_duration(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        return jsonify({"error": f"Could not read video: {e}"}), 400

    MEDIA_REGISTRY[media_id] = {
        "path": dest,
        "duration": duration,
        "filename": secure_filename(f.filename)
    }
    return jsonify({
        "id": media_id,
        "duration": duration,
        "url": f"/media/{media_id}",
        "filename": secure_filename(f.filename)
    })


@app.route("/api/youtube", methods=["POST"])
def api_youtube():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    use_cookies = bool(data.get("use_chrome_cookies"))

    if not YOUTUBE_URL_RE.match(url):
        return jsonify({"error": "Only youtube.com / youtu.be URLs are accepted."}), 400

    try:
        import yt_dlp
    except ImportError:
        return jsonify({"error": "yt-dlp is not installed."}), 500

    media_id = new_id()
    out_template = str(MEDIA_DIR / f"{media_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": out_template,
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 2 * 1024 * 1024 * 1024,
        "writethumbnail": False,
        "writeinfojson": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
    }
    if use_cookies:
        # Reads cookies from the local Chrome install on this machine only.
        ydl_opts["cookiesfrombrowser"] = ("chrome",)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get("title", f"video_{media_id}")
    except Exception as e:
        return jsonify({"error": f"Download failed: {e}"}), 400

    dest = MEDIA_DIR / f"{media_id}.mp4"
    if not dest.exists():
        candidates = list(MEDIA_DIR.glob(f"{media_id}.*"))
        if not candidates:
            return jsonify({"error": "Download produced no file."}), 500
        dest = candidates[0]

    try:
        duration = ffprobe_duration(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        return jsonify({"error": f"Could not read downloaded video: {e}"}), 400

    MEDIA_REGISTRY[media_id] = {
        "path": dest,
        "duration": duration,
        "filename": f"{video_title}.mp4"
    }
    return jsonify({
        "id": media_id,
        "duration": duration,
        "url": f"/media/{media_id}",
        "filename": f"{video_title}.mp4",
        "title": video_title
    })


@app.route("/media/<media_id>")
def serve_media(media_id):
    entry = MEDIA_REGISTRY.get(media_id)
    if not entry:
        abort(404)
    path: Path = entry["path"]
    return send_file(path, conditional=True)


@app.route("/api/download/<media_id>")
def api_download(media_id):
    entry = MEDIA_REGISTRY.get(media_id)
    if not entry:
        abort(404)
    
    path: Path = entry["path"]
    filename = entry.get("filename", path.name)
    
    return send_file(
        path,
        as_attachment=True,
        download_name=filename,
        mimetype="video/mp4"
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5005, debug=debug)
