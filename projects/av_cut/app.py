"""
Media Editor — Flask app
Load media (upload or URL) -> preview & cut chunks with ffmpeg -> transcribe
(openai-whisper / faster-whisper / mlx-whisper) with optional speaker
diarization (pyannote.audio or an LLM-based heuristic via Claude/Gemini) ->
download the transcript and/or a zip of everything.

Run:
    pip install -r requirements.txt
    python app.py
"""

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import (
    Flask, request, session, jsonify, send_file, abort, render_template_string
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("MEDIA_EDITOR_SECRET", os.urandom(32))

BASE_DIR = os.path.join(tempfile.gettempdir(), "media_editor_sessions")
os.makedirs(BASE_DIR, exist_ok=True)

# in-memory session registry: sid -> {dir, source, chunks, transcript, segments}
SESSIONS = {}

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


# --------------------------------------------------------------------------
# session / filesystem helpers
# --------------------------------------------------------------------------

def ensure_sid():
    sid = session.get("sid")
    if not sid:
        sid = uuid4().hex
        session["sid"] = sid
    return sid


def get_sid_or_none():
    return session.get("sid")


def get_session(sid, create=False):
    sess = SESSIONS.get(sid)
    if sess is None and create:
        d = os.path.join(BASE_DIR, sid)
        os.makedirs(d, exist_ok=True)
        sess = {"dir": d, "source": None, "chunks": [], "transcript": None, "segments": []}
        SESSIONS[sid] = sess
    return sess


def wipe_session_dir(sess):
    if os.path.isdir(sess["dir"]):
        shutil.rmtree(sess["dir"], ignore_errors=True)
    os.makedirs(sess["dir"], exist_ok=True)
    sess["source"] = None
    sess["chunks"] = []
    sess["transcript"] = None
    sess["segments"] = []


def fmt_ts(t):
    t = max(0.0, float(t))
    m = int(t // 60)
    s = t - m * 60
    return f"{m:02d}:{s:05.2f}"


# --------------------------------------------------------------------------
# media probing / cutting (ffmpeg / ffprobe)
# --------------------------------------------------------------------------

def probe_media(path):
    """Return {'kind': 'video'|'audio', 'duration': float} or None on failure."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, check=True, timeout=30,
        )
        data = json.loads(out.stdout.decode("utf-8", errors="ignore"))
    except Exception:
        return None

    duration = None
    fmt = data.get("format", {})
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except ValueError:
            duration = None

    has_video = False
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and s.get("codec_name") not in ("mjpeg", "png", "bmp"):
            has_video = True
        if duration is None and s.get("duration"):
            try:
                duration = max(duration or 0.0, float(s["duration"]))
            except ValueError:
                pass

    if duration is None:
        return None
    return {"kind": "video" if has_video else "audio", "duration": duration}


def cut_chunk(source_path, kind, start, end, out_path):
    cmd = ["ffmpeg", "-y", "-i", source_path, "-ss", f"{start:.3f}", "-to", f"{end:.3f}"]
    if kind == "video":
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart"]
    else:
        cmd += ["-vn", "-c:a", "aac"]
    cmd += [out_path]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)


# --------------------------------------------------------------------------
# transcription engines
# --------------------------------------------------------------------------

def run_whisper_openai(path, language, device, model_size):
    try:
        import whisper
    except ImportError:
        raise RuntimeError("openai-whisper is not installed on the server (pip install openai-whisper).")
    model = whisper.load_model(model_size, device=device)
    result = model.transcribe(path, language=language, verbose=False)
    return [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in result["segments"]]


def run_faster_whisper(path, language, device, model_size):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper is not installed on the server (pip install faster-whisper).")
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(path, language=language)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


def run_mlx_whisper(path, language, model_size):
    try:
        import whispermlx
    except ImportError:
        raise RuntimeError("whispermlx is not installed on the server (pip install whispermlx, Apple Silicon only).")
    repo = f"mlx-community/whisper-{model_size}-mlx"
    result = whispermlx.transcribe(path, path_or_hf_repo=repo, language=language, output_format='json')
    return [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in result["segments"]]


def transcribe_file(path, engine, language, device, model_size):
    if engine == "openai-whisper":
        return run_whisper_openai(path, language, device, model_size)
    if engine == "faster":
        return run_faster_whisper(path, language, device, model_size)
    if engine == "mlx":
        return run_mlx_whisper(path, language, model_size)
    raise RuntimeError(f"Unknown transcription engine '{engine}'.")


# --------------------------------------------------------------------------
# diarization
# --------------------------------------------------------------------------

def run_pyannote(path, hf_token, num_speakers=None):
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        raise RuntimeError("pyannote.audio is not installed on the server (pip install pyannote.audio).")
    if not hf_token:
        raise RuntimeError("A Hugging Face access token is required for pyannote diarization.")
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=hf_token)
    diarization = pipeline(path, num_speakers=num_speakers) if num_speakers else pipeline(path)

    turns = []
    for turn, speaker in diarization.speaker_diarization:
        turns.append({"start": turn.start, "end": turn.end, "speaker": speaker})
    return turns

def assign_speakers_from_turns(segments, turns):
    if not turns:
        for seg in segments:
            seg["speaker"] = "SPEAKER_00"
        return
    for seg in segments:
        best, best_overlap = None, 0.0
        for t in turns:
            overlap = min(seg["end"], t["end"]) - max(seg["start"], t["start"])
            if overlap > best_overlap:
                best_overlap, best = overlap, t
        if best is None:
            # fall back to nearest turn by start time
            best = min(turns, key=lambda t: abs(t["start"] - seg["start"]))
        seg["speaker"] = best["speaker"]


def run_ai_diarization(segments, provider, api_key, num_speakers=None, speaker_names=None):
    """Heuristic, text-based speaker labeling via an LLM (no separate audio model)."""
    if not api_key:
        raise RuntimeError("An API key is required for AI-based diarization.")

    payload = [{"i": i, "start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"]}
               for i, s in enumerate(segments)]

    constraint = ""
    if speaker_names:
        constraint = f"There are exactly {len(speaker_names)} speakers, named (in some order): {speaker_names}. Use these exact names as labels."
    elif num_speakers:
        constraint = f"There are exactly {num_speakers} speakers. Label them SPEAKER_00, SPEAKER_01, ... "
    else:
        constraint = "Infer a reasonable number of distinct speakers from context and label them SPEAKER_00, SPEAKER_01, ..."

    prompt = (
        "You are labeling speaker turns in a transcript based only on the text and timing below "
        "(no audio). " + constraint + " Respond with ONLY a JSON array of strings, one label per "
        "segment, in the same order as the input, and nothing else.\n\n"
        f"Segments: {json.dumps(payload)}"
    )

    if provider == "claude":
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("The 'anthropic' package is not installed on the server (pip install anthropic).")
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    elif provider == "gemini":
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError("The 'google-generativeai' package is not installed on the server (pip install google-generativeai).")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
        text = model.generate_content(prompt).text
    else:
        raise RuntimeError(f"Unknown AI provider '{provider}'.")

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise RuntimeError("The AI diarization response could not be parsed as JSON.")
    labels = json.loads(match.group(0))
    if len(labels) != len(segments):
        raise RuntimeError("The AI diarization response did not label every segment.")
    return labels


# --------------------------------------------------------------------------
# routes — pages / media
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/media/<sid>/source")
def media_source(sid):
    sess = SESSIONS.get(sid)
    if not sess or not sess.get("source"):
        abort(404)
    return send_file(sess["source"]["path"], conditional=True)


# --------------------------------------------------------------------------
# routes — API
# --------------------------------------------------------------------------

@app.route("/api/load", methods=["POST"])
def api_load():
    sid = ensure_sid()
    sess = get_session(sid, create=True)
    wipe_session_dir(sess)

    src_path = None
    up = request.files.get("file")
    url = (request.form.get("url") or "").strip()

    if up and up.filename:
        ext = os.path.splitext(secure_filename(up.filename))[1].lower() or ".mp4"
        src_path = os.path.join(sess["dir"], f"source{ext}")
        up.save(src_path)
    elif url:
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext not in VIDEO_EXTS | AUDIO_EXTS:
            ext = ".mp4"
        src_path = os.path.join(sess["dir"], f"source{ext}")
        try:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(src_path, "wb") as fh:
                    for chunk in r.iter_content(65536):
                        fh.write(chunk)
        except Exception as e:
            return jsonify(error=f"Could not download that URL ({e})."), 400
    else:
        return jsonify(error="Provide a file or a URL."), 400

    info = probe_media(src_path)
    if info is None:
        return jsonify(error="That file doesn't look like a media file ffmpeg can read."), 400

    sess["source"] = {
        "path": src_path,
        "ext": os.path.splitext(src_path)[1],
        "kind": info["kind"],
        "duration": info["duration"],
    }
    return jsonify(kind=info["kind"], duration=info["duration"], src=f"/media/{sid}/source")


@app.route("/api/chunk", methods=["POST"])
def api_add_chunk():
    sid = get_sid_or_none()
    sess = get_session(sid) if sid else None
    if not sess or not sess.get("source"):
        return jsonify(error="Load a media file first."), 400

    data = request.get_json(force=True, silent=True) or {}
    try:
        start = float(data.get("start"))
        end = float(data.get("end"))
    except (TypeError, ValueError):
        return jsonify(error="Invalid start/end."), 400

    dur = sess["source"]["duration"]
    start = max(0.0, min(start, dur))
    end = max(0.0, min(end, dur))
    if end - start < 0.05:
        return jsonify(error="End must be at least 0.05s after start."), 400

    idx = (max((c["id"] for c in sess["chunks"]), default=0)) + 1
    kind = sess["source"]["kind"]
    out_ext = ".mp4" if kind == "video" else ".m4a"
    chunks_dir = os.path.join(sess["dir"], "chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    out_path = os.path.join(chunks_dir, f"chunk_{idx}{out_ext}")

    try:
        cut_chunk(sess["source"]["path"], kind, start, end, out_path)
    except subprocess.CalledProcessError as e:
        return jsonify(error=f"ffmpeg failed: {e.stderr.decode(errors='ignore')[-400:]}"), 500

    sess["chunks"].append({
        "id": idx, "start": start, "end": end, "duration": end - start,
        "path": out_path, "filename": os.path.basename(out_path),
    })
    return jsonify(chunks=[{k: v for k, v in c.items() if k != "path"} for c in sess["chunks"]])


@app.route("/api/chunk/<int:cid>", methods=["DELETE"])
def api_delete_chunk(cid):
    sid = get_sid_or_none()
    sess = get_session(sid) if sid else None
    if not sess:
        return jsonify(error="No session."), 400
    keep, drop = [], []
    for c in sess["chunks"]:
        (drop if c["id"] == cid else keep).append(c)
    for c in drop:
        try:
            os.remove(c["path"])
        except OSError:
            pass
    sess["chunks"] = keep
    return jsonify(chunks=[{k: v for k, v in c.items() if k != "path"} for c in sess["chunks"]])


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    sid = get_sid_or_none()
    sess = get_session(sid) if sid else None
    if not sess or not sess.get("source"):
        return jsonify(error="Load a media file first."), 400

    d = request.get_json(force=True, silent=True) or {}
    engine = d.get("engine")
    language = d.get("language")
    device = d.get("device")
    model_size = d.get("model_size")
    diarize = bool(d.get("diarize"))
    diarize_method = d.get("diarize_method")           # 'pyannote' | 'ai_api'
    ai_provider = d.get("ai_provider")                  # 'gemini' | 'claude'
    api_key = d.get("api_key")
    name_speakers = bool(d.get("name_speakers"))
    speaker_mode = d.get("speaker_mode")                # 'count' | 'names'
    speaker_count = d.get("speaker_count")
    speaker_names = d.get("speaker_names") or []

    sources = sess["chunks"] if sess["chunks"] else [{
        "start": 0.0, "path": sess["source"]["path"],
    }]
    sources = sorted(sources, key=lambda c: c.get("start", 0.0))

    all_segments = []
    try:
        for item in sources:
            segs = transcribe_file(item["path"], engine, language, device, model_size)
            offset = item.get("start", 0.0)
            for s in segs:
                all_segments.append({"start": s["start"] + offset, "end": s["end"] + offset, "text": s["text"]})
    except RuntimeError as e:
        return jsonify(error=str(e)), 500
    except Exception as e:
        return jsonify(error=f"Transcription failed: {e}"), 500

    if diarize:
        num_speakers = int(speaker_count) if (name_speakers and speaker_mode == "count" and speaker_count) else None
        names = speaker_names if (name_speakers and speaker_mode == "names" and speaker_names) else None
        try:
            if diarize_method == "pyannote":
                turns = []
                for item in sources:
                    t = run_pyannote(item["path"], api_key, num_speakers)
                    off = item.get("start", 0.0)
                    for x in t:
                        turns.append({"start": x["start"] + off, "end": x["end"] + off, "speaker": x["speaker"]})
                assign_speakers_from_turns(all_segments, turns)
                if names:
                    mapping = {}
                    for seg in all_segments:
                        if seg["speaker"] not in mapping:
                            mapping[seg["speaker"]] = names[len(mapping)] if len(mapping) < len(names) else seg["speaker"]
                    for seg in all_segments:
                        seg["speaker"] = mapping[seg["speaker"]]
            elif diarize_method == "ai_api":
                labels = run_ai_diarization(all_segments, ai_provider, api_key, num_speakers, names)
                for seg, label in zip(all_segments, labels):
                    seg["speaker"] = label
            else:
                return jsonify(error="Choose a diarization method (pyannote or AI API)."), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 500
        except Exception as e:
            return jsonify(error=f"Diarization failed: {e}"), 500

    lines = []
    for seg in all_segments:
        prefix = f"{seg['speaker']}: " if seg.get("speaker") else ""
        lines.append(f"[{fmt_ts(seg['start'])} - {fmt_ts(seg['end'])}] {prefix}{seg['text']}")
    transcript = "\n".join(lines)
    sess["transcript"] = transcript
    sess["segments"] = all_segments
    return jsonify(transcript=transcript, segments=all_segments)


@app.route("/api/download/transcription")
def download_transcription():
    sid = get_sid_or_none()
    sess = get_session(sid) if sid else None
    if not sess or not sess.get("transcript"):
        abort(404)
    buf = io.BytesIO(sess["transcript"].encode("utf-8"))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="transcription.txt", mimetype="text/plain")


@app.route("/api/download/zip")
def download_zip():
    sid = get_sid_or_none()
    sess = get_session(sid) if sid else None
    if not sess or not sess.get("source"):
        abort(404)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if sess.get("transcript"):
            z.writestr("transcription.txt", sess["transcript"])
        if sess["chunks"]:
            for c in sess["chunks"]:
                if os.path.exists(c["path"]):
                    z.write(c["path"], arcname=f"chunks/{c['filename']}")
        else:
            z.write(sess["source"]["path"], arcname=f"source{sess['source']['ext']}")
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="media_editor_export.zip", mimetype="application/zip")


# --------------------------------------------------------------------------
# frontend
# --------------------------------------------------------------------------

INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Media editor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0b0c0e; --panel:#16181b; --panel-2:#1c1f23; --border:#2b2f34;
  --text:#edebe6; --text-dim:#9296a0; --text-faint:#5c6068;
  --amber:#e8a33d; --amber-dim:#8a6428; --teal:#5eead4; --red:#e5484d;
  --radius:10px;
  --font-display:'Space Grotesk',sans-serif; --font-body:'Inter',sans-serif; --font-mono:'IBM Plex Mono',monospace;
}
*{box-sizing:border-box;}
html,body{height:100%;}
body{
  margin:0; background:var(--bg); color:var(--text); font-family:var(--font-body);
  display:flex; flex-direction:column; overflow:hidden;
}
::selection{background:var(--amber); color:#161616;}
::-webkit-scrollbar{width:10px; height:10px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--border); border-radius:6px;}
::-webkit-scrollbar-thumb:hover{background:var(--text-faint);}

header{
  flex:0 0 auto; padding:14px 22px; border-bottom:1px solid var(--border);
  position:relative; overflow:hidden;
  background:
    repeating-linear-gradient(115deg, rgba(232,163,61,0.05) 0 2px, transparent 2px 26px),
    var(--panel);
}
header h2{
  margin:0; font-family:var(--font-display); font-weight:600; font-size:17px;
  letter-spacing:0.02em; display:flex; align-items:center; gap:10px;
}
header h2::before{
  content:''; width:9px; height:9px; border-radius:50%; background:var(--amber);
  box-shadow:0 0 10px 1px var(--amber); flex:0 0 auto;
}

main{flex:1 1 auto; min-height:0; display:flex; padding:16px 22px 22px;}
.main-container{
  flex:1; min-height:0; display:flex; flex-direction:column;
  border:1px solid var(--border); border-radius:var(--radius); background:var(--panel);
  overflow:hidden;
}

.tabs{flex:1; min-height:0; display:flex; flex-direction:column;}
.tab-nav{
  flex:0 0 auto; display:flex; border-bottom:1px solid var(--border); background:var(--panel-2);
  overflow-x:auto;
}
.tab-nav button{
  font-family:var(--font-body); font-weight:600; font-size:13px; color:var(--text-dim);
  background:none; border:none; padding:13px 18px 11px; cursor:pointer; white-space:nowrap;
  border-bottom:2px solid transparent; display:flex; align-items:center; gap:8px;
  transition:color .15s;
}
.tab-nav button .eyebrow{
  font-family:var(--font-mono); font-size:10px; color:var(--text-faint); letter-spacing:.05em;
}
.tab-nav button:hover{color:var(--text);}
.tab-nav button.active{color:var(--text); border-bottom-color:var(--amber);}
.tab-nav button.active .eyebrow{color:var(--amber);}
.tab-nav button:disabled{color:var(--text-faint); cursor:not-allowed;}

.tab-panel{display:none; flex:1; min-height:0; overflow-y:auto; padding:20px 24px 28px;}
.tab-panel.active{display:flex; flex-direction:column; gap:18px;}

.field{display:flex; flex-direction:column; gap:6px;}
.field label{font-size:12px; color:var(--text-dim); font-weight:500;}
.row{display:flex; gap:14px; flex-wrap:wrap;}
.row > .field{flex:1; min-width:150px;}

select, input[type=text], input[type=url], input[type=number], textarea{
  background:var(--panel-2); border:1px solid var(--border); color:var(--text);
  border-radius:7px; padding:9px 11px; font-family:var(--font-body); font-size:13.5px;
  outline:none; transition:border-color .15s;
}
select:focus, input:focus, textarea:focus{border-color:var(--amber);}
select:disabled, input:disabled{opacity:.4; cursor:not-allowed;}

input[type=file]{color:var(--text-dim); font-size:13px;}

.btn{
  font-family:var(--font-body); font-weight:600; font-size:13.5px; cursor:pointer;
  border-radius:7px; padding:10px 18px; border:1px solid var(--amber); background:var(--amber);
  color:#181205; transition:filter .15s, transform .05s;
}
.btn:hover{filter:brightness(1.08);}
.btn:active{transform:translateY(1px);}
.btn:disabled{background:var(--panel-2); border-color:var(--border); color:var(--text-faint); cursor:not-allowed;}
.btn.secondary{background:transparent; color:var(--text); border-color:var(--border);}
.btn.secondary:hover{border-color:var(--text-dim); filter:none;}
.btn.small{padding:6px 11px; font-size:12px;}
.btn.danger{background:transparent; border-color:var(--red); color:var(--red);}

fieldset{border:1px solid var(--border); border-radius:9px; padding:14px 16px; margin:0; display:flex; flex-direction:column; gap:12px;}
fieldset[disabled]{opacity:.35;}
legend{font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--text-dim); padding:0 6px;}

.checkline{display:flex; align-items:center; gap:9px; font-size:13.5px;}
.checkline input[type=checkbox]{accent-color:var(--amber); width:15px; height:15px;}
.subrow{margin-left:26px; display:flex; flex-direction:column; gap:10px;}

.hidden{display:none !important;}

/* --- load tab --- */
.mode-toggle{display:flex; gap:0; width:fit-content; border:1px solid var(--border); border-radius:8px; overflow:hidden;}
.mode-toggle button{
  background:var(--panel-2); border:none; color:var(--text-dim); padding:8px 16px; font-size:13px;
  font-family:var(--font-body); font-weight:500; cursor:pointer;
}
.mode-toggle button.active{background:var(--amber); color:#181205; font-weight:600;}

/* --- preview & cut --- */
.preview-wrap{background:#000; border:1px solid var(--border); border-radius:9px; overflow:hidden; max-height:38vh; display:flex; align-items:center; justify-content:center;}
video, audio{width:100%; display:block;}
audio{padding:16px;}
.timeline{display:flex; flex-direction:column; gap:8px;}
.ruler{
  height:16px; border-radius:3px; position:relative;
  background:repeating-linear-gradient(90deg, var(--border) 0 1px, transparent 1px 20px);
}
.range-stack{position:relative; height:30px;}
.range-stack input[type=range]{
  position:absolute; left:0; right:0; top:0; width:100%; margin:0; height:30px;
  background:none; -webkit-appearance:none; pointer-events:none;
}
.range-stack input[type=range]::-webkit-slider-runnable-track{height:4px; background:var(--border); border-radius:2px;}
.range-stack input[type=range]::-webkit-slider-thumb{
  -webkit-appearance:none; pointer-events:auto; width:16px; height:16px; border-radius:50%;
  margin-top:-6px; cursor:grab; border:2px solid #0b0c0e;
}
#startRange::-webkit-slider-thumb{background:var(--teal);}
#endRange::-webkit-slider-thumb{background:var(--amber);}
.range-stack input[type=range]::-moz-range-thumb{
  pointer-events:auto; width:16px; height:16px; border-radius:50%; border:2px solid #0b0c0e; cursor:grab;
}
#startRange::-moz-range-thumb{background:var(--teal);}
#endRange::-moz-range-thumb{background:var(--amber);}

.timers{display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap;}
.timer-box{display:flex; flex-direction:column; gap:5px;}
.timer-box .tag{font-family:var(--font-mono); font-size:10.5px; letter-spacing:.05em;}
.timer-box.start .tag{color:var(--teal);}
.timer-box.end .tag{color:var(--amber);}
.timer-box input{font-family:var(--font-mono); width:110px;}
.timer-actions{display:flex; gap:6px;}

ul#chunkList{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px;}
ul#chunkList li{
  display:flex; align-items:center; justify-content:space-between; gap:10px;
  background:var(--panel-2); border:1px solid var(--border); border-radius:7px; padding:9px 12px;
  font-family:var(--font-mono); font-size:12.5px;
}
ul#chunkList li .meta{color:var(--text-dim);}
ul#chunkList li .idx{color:var(--amber); font-weight:600;}
.empty-note{color:var(--text-faint); font-size:12.5px; font-style:italic;}

/* --- transcription tab --- */
.speaker-name-list{display:flex; flex-direction:column; gap:8px;}
.speaker-name-list .sn-row{display:flex; gap:8px; align-items:center;}
.speaker-name-list .sn-row span{font-family:var(--font-mono); color:var(--text-faint); font-size:11.5px; width:64px;}

/* --- extract tab --- */
textarea#transcriptOut{flex:1; min-height:220px; resize:vertical; font-family:var(--font-mono); font-size:12.5px; line-height:1.6;}
.download-row{display:flex; gap:10px; flex-wrap:wrap;}

.toast{
  position:fixed; bottom:18px; left:50%; transform:translateX(-50%) translateY(10px);
  background:#20120f; border:1px solid var(--red); color:#ffd8d6; padding:11px 18px;
  border-radius:8px; font-size:13px; max-width:min(560px,90vw); opacity:0; pointer-events:none;
  transition:opacity .2s, transform .2s; z-index:50;
}
.toast.show{opacity:1; transform:translateX(-50%) translateY(0);}

.spinner{
  width:14px; height:14px; border-radius:50%; border:2px solid rgba(0,0,0,.25);
  border-top-color:#181205; animation:spin .7s linear infinite; display:inline-block; vertical-align:-2px;
}
@keyframes spin{to{transform:rotate(360deg);}}

footer{flex:0 0 auto; padding:9px 22px; text-align:center; font-size:11px; color:var(--text-faint); font-family:var(--font-mono);}

@media (max-width:720px){
  main{padding:10px;}
  header{padding:12px 16px;}
  .tab-nav button{padding:11px 12px 9px; font-size:12px;}
  .tab-panel{padding:16px;}
  .row > .field{min-width:120px;}
  .preview-wrap{max-height:26vh;}
}
</style>
</head>
<body>

<header><h2>Media editor</h2></header>

<main>
  <div class="main-container">
    <div class="tabs">
      <div class="tab-nav">
        <button class="tab-btn active" data-tab="load"><span class="eyebrow">01</span>Load media</button>
        <button class="tab-btn" data-tab="cut" disabled><span class="eyebrow">02</span>Preview &amp; cut</button>
        <button class="tab-btn" data-tab="transcribe" disabled><span class="eyebrow">03</span>Transcription</button>
        <button class="tab-btn" data-tab="extract" disabled><span class="eyebrow">04</span>Results</button>
      </div>

      <!-- TAB 1: load media -->
      <div class="tab-panel active" data-panel="load">
        <div class="field">
          <label>Source</label>
          <div class="mode-toggle">
            <button type="button" id="modeUpload" class="active">Upload file</button>
            <button type="button" id="modeUrl">Enter URL</button>
          </div>
        </div>
        <div class="field" id="uploadField">
          <label for="fileInput">Media file</label>
          <input type="file" id="fileInput" accept="video/*,audio/*">
        </div>
        <div class="field hidden" id="urlField">
          <label for="urlInput">Media URL</label>
          <input type="url" id="urlInput" placeholder="https://example.com/clip.mp4">
        </div>
        <div><button class="btn" id="loadBtn">Load file</button></div>
      </div>

      <!-- TAB 2: preview and cut -->
      <div class="tab-panel" data-panel="cut">
        <div class="preview-wrap" id="previewWrap">
          <video id="videoPreview" controls></video>
        </div>
        <div class="timeline">
          <div class="ruler"></div>
          <div class="range-stack">
            <input type="range" id="startRange" min="0" max="100" step="0.01" value="0">
            <input type="range" id="endRange" min="0" max="100" step="0.01" value="100">
          </div>
        </div>
        <div class="timers">
          <div class="timer-box start">
            <span class="tag">IN</span>
            <input type="text" id="startTimer" value="00:00.00">
            <div class="timer-actions"><button class="btn secondary small" id="setStartBtn">Use playhead</button></div>
          </div>
          <div class="timer-box end">
            <span class="tag">OUT</span>
            <input type="text" id="endTimer" value="00:00.00">
            <div class="timer-actions"><button class="btn secondary small" id="setEndBtn">Use playhead</button></div>
          </div>
          <button class="btn" id="addChunkBtn">Add chunk</button>
        </div>
        <div class="field">
          <label>Chunks</label>
          <ul id="chunkList"></ul>
          <div class="empty-note" id="chunkEmptyNote">No chunks yet — transcription will use the full file.</div>
        </div>
      </div>

      <!-- TAB 3: transcription controls -->
      <div class="tab-panel" data-panel="transcribe">
        <div class="row">
          <div class="field">
            <label for="engineSel">Engine</label>
            <select id="engineSel">
              <option value="openai-whisper">openai-whisper</option>
              <option value="faster">faster-whisper</option>
              <option value="mlx">mlx-whisper (Apple Silicon)</option>
            </select>
          </div>
          <div class="field">
            <label for="langSel">Language</label>
            <select id="langSel">
              <option value="de">German</option>
              <option value="en" selected>English</option>
              <option value="fr">French</option>
              <option value="ro">Romanian</option>
            </select>
          </div>
          <div class="field">
            <label for="deviceSel">Device</label>
            <select id="deviceSel">
              <option value="cpu">CPU</option>
              <option value="cuda">CUDA</option>
              <option value="metal">Metal</option>
            </select>
          </div>
          <div class="field">
            <label for="modelSel">Model size</label>
            <select id="modelSel">
              <option value="tiny">tiny</option>
              <option value="base">base</option>
              <option value="small" selected>small</option>
              <option value="medium">medium</option>
              <option value="large-v3">large-v3</option>
            </select>
          </div>
        </div>

        <div class="checkline">
          <input type="checkbox" id="diarizeCk"><label for="diarizeCk">Identify speakers (diarization)</label>
        </div>

        <fieldset id="diarizeFields" disabled>
          <legend>Speaker identification</legend>

          <div class="checkline">
            <input type="checkbox" id="pyannoteCk"><label for="pyannoteCk">pyannote.audio (audio-based, needs a Hugging Face token)</label>
          </div>
          <div class="checkline">
            <input type="checkbox" id="aiApiCk"><label for="aiApiCk">AI API (text-based heuristic labeling)</label>
          </div>
          <div class="subrow hidden" id="aiApiSub">
            <div class="field" style="max-width:220px">
              <label for="aiProviderSel">Provider</label>
              <select id="aiProviderSel">
                <option value="gemini">Gemini</option>
                <option value="claude">Claude</option>
              </select>
            </div>
          </div>

          <div class="checkline">
            <input type="checkbox" id="nameSpeakersCk"><label for="nameSpeakersCk">Name the speakers</label>
          </div>
          <div class="subrow hidden" id="nameSpeakersSub">
            <div class="checkline">
              <input type="radio" name="speakerMode" id="speakerCountRb" checked>
              <label for="speakerCountRb">I just know how many speakers</label>
              <input type="number" id="speakerCountInput" min="1" max="20" value="2" style="width:64px; margin-left:8px;">
            </div>
            <div class="checkline">
              <input type="radio" name="speakerMode" id="speakerNamesRb">
              <label for="speakerNamesRb">I'll name each speaker</label>
            </div>
            <div class="speaker-name-list hidden" id="speakerNameList">
              <div class="sn-row"><span>Speaker 1</span><input type="text" class="snInput" placeholder="e.g. Alex"></div>
              <div class="sn-row"><span>Speaker 2</span><input type="text" class="snInput" placeholder="e.g. Jordan"></div>
              <button class="btn secondary small" id="addSpeakerNameBtn" style="width:fit-content">+ add speaker</button>
            </div>
          </div>

          <div class="checkline">
            <input type="checkbox" id="apiKeyCk" disabled><label for="apiKeyCk">API key</label>
          </div>
          <div class="subrow hidden" id="apiKeySub">
            <input type="text" id="apiKeyInput" placeholder="Paste key or token">
          </div>
        </fieldset>

        <div><button class="btn" id="transcribeBtn">Transcribe</button></div>
      </div>

      <!-- TAB 4: extract results -->
      <div class="tab-panel" data-panel="extract" style="flex:1;">
        <textarea id="transcriptOut" placeholder="Your transcription will appear here." readonly></textarea>
        <div class="download-row">
          <button class="btn secondary" id="downloadTxtBtn">Download transcription</button>
          <button class="btn secondary" id="downloadZipBtn">Download zip file</button>
        </div>
      </div>

    </div>
  </div>
</main>

<footer>
  <div class="copyright-notice">© 2026 Media Editor — local ffmpeg &amp; Whisper processing</div>
</footer>

<div class="toast" id="toast"></div>

<script>
const state = { kind:null, duration:0, chunks:[] };

// ---------- utils ----------
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._h);
  toast._h = setTimeout(()=>t.classList.remove('show'), 4200000);
}
function fmtTs(t){
  t = Math.max(0,t);
  const m = Math.floor(t/60);
  const s = (t - m*60).toFixed(2).padStart(5,'0');
  return `${String(m).padStart(2,'0')}:${s}`;
}
function parseTs(str){
  const m = str.trim().match(/^(\d+):(\d+(?:\.\d+)?)$/);
  if(!m) return null;
  return parseInt(m[1],10)*60 + parseFloat(m[2]);
}
async function api(url, opts){
  const res = await fetch(url, opts);
  let data = null;
  try{ data = await res.json(); }catch(e){}
  if(!res.ok){
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

// ---------- tabs ----------
const tabButtons = document.querySelectorAll('.tab-btn');
tabButtons.forEach(btn=>{
  btn.addEventListener('click', ()=>{
    if(btn.disabled) return;
    tabButtons.forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).classList.add('active');
  });
});
function goTab(name){ document.querySelector(`.tab-btn[data-tab="${name}"]`).click(); }
function unlockTabs(){ tabButtons.forEach(b=>{ if(b.dataset.tab!=='load') b.disabled=false; }); }

// ---------- tab 1: load ----------
const modeUpload = document.getElementById('modeUpload');
const modeUrl = document.getElementById('modeUrl');
const uploadField = document.getElementById('uploadField');
const urlField = document.getElementById('urlField');
modeUpload.addEventListener('click', ()=>{
  modeUpload.classList.add('active'); modeUrl.classList.remove('active');
  uploadField.classList.remove('hidden'); urlField.classList.add('hidden');
  document.getElementById('loadBtn').textContent = 'Load file';
});
modeUrl.addEventListener('click', ()=>{
  modeUrl.classList.add('active'); modeUpload.classList.remove('active');
  urlField.classList.remove('hidden'); uploadField.classList.add('hidden');
  document.getElementById('loadBtn').textContent = 'Load from URL';
});

const previewWrap = document.getElementById('previewWrap');
let mediaEl = document.getElementById('videoPreview');

document.getElementById('loadBtn').addEventListener('click', async ()=>{
  const btn = document.getElementById('loadBtn');
  const fd = new FormData();
  if(modeUpload.classList.contains('active')){
    const f = document.getElementById('fileInput').files[0];
    if(!f){ toast('Choose a file first.'); return; }
    fd.append('file', f);
  } else {
    const u = document.getElementById('urlInput').value.trim();
    if(!u){ toast('Enter a URL first.'); return; }
    fd.append('url', u);
  }
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Loading…';
  try{
    const data = await api('/api/load', {method:'POST', body: fd});
    state.kind = data.kind; state.duration = data.duration; state.chunks = [];
    setupPreviewElement(data.kind, data.src);
    resetCutUI();
    renderChunkList();
    unlockTabs();
    goTab('cut');
  }catch(e){ toast(e.message); }
  finally{ btn.disabled = false; btn.textContent = modeUpload.classList.contains('active') ? 'Load file' : 'Load from URL'; }
});

function setupPreviewElement(kind, src){
  previewWrap.innerHTML = '';
  if(kind === 'video'){
    mediaEl = document.createElement('video');
    mediaEl.id = 'videoPreview'; mediaEl.controls = true;
  } else {
    mediaEl = document.createElement('audio');
    mediaEl.id = 'videoPreview'; mediaEl.controls = true;
  }
  mediaEl.src = src;
  previewWrap.appendChild(mediaEl);
}

// ---------- tab 2: preview & cut ----------
const startRange = document.getElementById('startRange');
const endRange = document.getElementById('endRange');
const startTimer = document.getElementById('startTimer');
const endTimer = document.getElementById('endTimer');

function resetCutUI(){
  startRange.min = 0; startRange.max = state.duration; startRange.step = 0.01; startRange.value = 0;
  endRange.min = 0; endRange.max = state.duration; endRange.step = 0.01; endRange.value = state.duration;
  startTimer.value = fmtTs(0);
  endTimer.value = fmtTs(state.duration);
}

function syncFromRanges(){
  let s = parseFloat(startRange.value), e = parseFloat(endRange.value);
  if(s > e - 0.05){ s = Math.max(0, e - 0.05); startRange.value = s; }
  startTimer.value = fmtTs(s);
  endTimer.value = fmtTs(e);
}
startRange.addEventListener('input', ()=>{ syncFromRanges(); if(mediaEl) mediaEl.currentTime = parseFloat(startRange.value); });
endRange.addEventListener('input', ()=>{ syncFromRanges(); if(mediaEl) mediaEl.currentTime = parseFloat(endRange.value); });

function syncFromTimers(which){
  const s = parseTs(startTimer.value), e = parseTs(endTimer.value);
  if(which==='start' && s!==null){ startRange.value = Math.min(Math.max(s,0), state.duration); }
  if(which==='end' && e!==null){ endRange.value = Math.min(Math.max(e,0), state.duration); }
  syncFromRanges();
}
startTimer.addEventListener('change', ()=>syncFromTimers('start'));
endTimer.addEventListener('change', ()=>syncFromTimers('end'));

document.getElementById('setStartBtn').addEventListener('click', ()=>{
  if(!mediaEl) return;
  startRange.value = mediaEl.currentTime; syncFromRanges();
});
document.getElementById('setEndBtn').addEventListener('click', ()=>{
  if(!mediaEl) return;
  endRange.value = mediaEl.currentTime; syncFromRanges();
});

document.getElementById('addChunkBtn').addEventListener('click', async ()=>{
  const btn = document.getElementById('addChunkBtn');
  const start = parseFloat(startRange.value), end = parseFloat(endRange.value);
  if(end - start < 0.05){ toast('Select a longer range first.'); return; }
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Cutting…';
  try{
    const data = await api('/api/chunk', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({start, end}),
    });
    state.chunks = data.chunks;
    renderChunkList();
  }catch(e){ toast(e.message); }
  finally{ btn.disabled = false; btn.textContent = 'Add chunk'; }
});

function renderChunkList(){
  const ul = document.getElementById('chunkList');
  ul.innerHTML = '';
  document.getElementById('chunkEmptyNote').classList.toggle('hidden', state.chunks.length>0);
  state.chunks.forEach(c=>{
    const li = document.createElement('li');
    li.innerHTML = `<span><span class="idx">#${c.id}</span> <span class="meta">${fmtTs(c.start)} – ${fmtTs(c.end)} (${c.duration.toFixed(2)}s)</span></span>`;
    const delBtn = document.createElement('button');
    delBtn.className = 'btn danger small'; delBtn.textContent = 'Remove';
    delBtn.addEventListener('click', async ()=>{
      try{
        const data = await api(`/api/chunk/${c.id}`, {method:'DELETE'});
        state.chunks = data.chunks; renderChunkList();
      }catch(e){ toast(e.message); }
    });
    li.appendChild(delBtn);
    ul.appendChild(li);
  });
}

// ---------- tab 3: transcription controls ----------
const engineSel = document.getElementById('engineSel');
const deviceSel = document.getElementById('deviceSel');
const diarizeCk = document.getElementById('diarizeCk');
const diarizeFields = document.getElementById('diarizeFields');
const pyannoteCk = document.getElementById('pyannoteCk');
const aiApiCk = document.getElementById('aiApiCk');
const aiApiSub = document.getElementById('aiApiSub');
const nameSpeakersCk = document.getElementById('nameSpeakersCk');
const nameSpeakersSub = document.getElementById('nameSpeakersSub');
const speakerCountRb = document.getElementById('speakerCountRb');
const speakerNamesRb = document.getElementById('speakerNamesRb');
const speakerCountInput = document.getElementById('speakerCountInput');
const speakerNameList = document.getElementById('speakerNameList');
const apiKeyCk = document.getElementById('apiKeyCk');
const apiKeySub = document.getElementById('apiKeySub');
const apiKeyInput = document.getElementById('apiKeyInput');

function updateDeviceOptions(){
  const mlx = engineSel.value === 'mlx';
  [...deviceSel.options].forEach(o=>{
    o.disabled = mlx ? o.value !== 'metal' : o.value === 'metal';
  });
  deviceSel.value = mlx ? 'metal' : (deviceSel.value === 'metal' ? 'cpu' : deviceSel.value);
  deviceSel.disabled = mlx; // forced to metal
}
engineSel.addEventListener('change', updateDeviceOptions);
updateDeviceOptions();

diarizeCk.addEventListener('change', ()=>{
  diarizeFields.disabled = !diarizeCk.checked;
  if(!diarizeCk.checked){
    pyannoteCk.checked = false; aiApiCk.checked = false; nameSpeakersCk.checked = false;
  }
  updateDiarizeUI();
});

function setMutex(checkedBox, otherBox){
  checkedBox.disabled = false; otherBox.disabled = checkedBox.checked;
}
pyannoteCk.addEventListener('change', ()=>{ if(pyannoteCk.checked) aiApiCk.checked = false; updateDiarizeUI(); });
aiApiCk.addEventListener('change', ()=>{ if(aiApiCk.checked) pyannoteCk.checked = false; updateDiarizeUI(); });

nameSpeakersCk.addEventListener('change', updateDiarizeUI);
speakerCountRb.addEventListener('change', updateDiarizeUI);
speakerNamesRb.addEventListener('change', updateDiarizeUI);

document.getElementById('addSpeakerNameBtn').addEventListener('click', ()=>{
  const rows = speakerNameList.querySelectorAll('.sn-row').length;
  const row = document.createElement('div');
  row.className = 'sn-row';
  row.innerHTML = `<span>Speaker ${rows+1}</span><input type="text" class="snInput" placeholder="name">`;
  speakerNameList.insertBefore(row, document.getElementById('addSpeakerNameBtn'));
});

function updateDiarizeUI(){
  setMutex(pyannoteCk, aiApiCk);
  setMutex(aiApiCk, pyannoteCk);
  aiApiSub.classList.toggle('hidden', !aiApiCk.checked);

  nameSpeakersSub.classList.toggle('hidden', !nameSpeakersCk.checked);
  speakerCountInput.disabled = !(nameSpeakersCk.checked && speakerCountRb.checked);
  speakerNameList.classList.toggle('hidden', !(nameSpeakersCk.checked && speakerNamesRb.checked));

  const needsKey = pyannoteCk.checked || aiApiCk.checked;
  apiKeyCk.checked = needsKey;
  apiKeySub.classList.toggle('hidden', !needsKey);
  apiKeyInput.placeholder = pyannoteCk.checked ? 'Hugging Face access token' : 'Provider API key';
}
updateDiarizeUI();

document.getElementById('transcribeBtn').addEventListener('click', async ()=>{
  const btn = document.getElementById('transcribeBtn');
  const diarize = diarizeCk.checked;
  if(diarize && !pyannoteCk.checked && !aiApiCk.checked){
    toast('Pick a diarization method: pyannote or AI API.'); return;
  }
  if(diarize && (pyannoteCk.checked || aiApiCk.checked) && !apiKeyInput.value.trim()){
    toast('An API key / token is required for the selected diarization method.'); return;
  }
  const speakerNames = [...speakerNameList.querySelectorAll('.snInput')].map(i=>i.value.trim()).filter(Boolean);

  const payload = {
    engine: engineSel.value,
    language: document.getElementById('langSel').value,
    device: deviceSel.value,
    model_size: document.getElementById('modelSel').value,
    diarize,
    diarize_method: pyannoteCk.checked ? 'pyannote' : (aiApiCk.checked ? 'ai_api' : null),
    ai_provider: document.getElementById('aiProviderSel').value,
    api_key: apiKeyInput.value.trim(),
    name_speakers: nameSpeakersCk.checked,
    speaker_mode: speakerCountRb.checked ? 'count' : 'names',
    speaker_count: speakerCountInput.value,
    speaker_names: speakerNames,
  };

  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Transcribing…';
  try{
    const data = await api('/api/transcribe', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload),
    });
    document.getElementById('transcriptOut').value = data.transcript;
    goTab('extract');
  }catch(e){ toast(e.message); }
  finally{ btn.disabled = false; btn.textContent = 'Transcribe'; }
});

// ---------- tab 4: results ----------
document.getElementById('downloadTxtBtn').addEventListener('click', ()=>{
  window.location.href = '/api/download/transcription';
});
document.getElementById('downloadZipBtn').addEventListener('click', ()=>{
  window.location.href = '/api/download/zip';
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5030)
