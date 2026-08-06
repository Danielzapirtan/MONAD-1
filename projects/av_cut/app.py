# app.py
from flask import Flask, request, jsonify, send_file
import os, io, zipfile, tempfile, uuid, json
from pathlib import Path

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB
UPLOAD_FOLDER = Path(tempfile.gettempdir()) / 'mediacutter'
UPLOAD_FOLDER.mkdir(exist_ok=True)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="description" content="Media cutter — trim video or audio, transcribe with Whisper"/>
<meta name="theme-color" content="#0f0f0f"/>
<title>Media cutter</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0f0f0f;
    --surface: #1a1a1a;
    --surface2: #242424;
    --border: #333;
    --accent: #7c6aff;
    --accent2: #5a4ecc;
    --text: #e8e8e8;
    --muted: #888;
    --danger: #e05252;
    --success: #52c07a;
    --radius: 8px;
    --font: 'Segoe UI', system-ui, sans-serif;
  }
  html, body { height: 100%; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 15px; }
  body { display: flex; flex-direction: column; min-height: 100vh; }
  header { padding: 1.2rem 2rem; background: var(--surface); border-bottom: 1px solid var(--border); }
  header h1 { font-size: 1.4rem; letter-spacing: .04em; color: var(--accent); }
  main { flex: 1; padding: 2rem; max-width: 960px; margin: 0 auto; width: 100%; }
  footer { text-align: center; padding: .8rem; color: var(--muted); font-size: .8rem; border-top: 1px solid var(--border); }

  /* Tabs */
  .tabs-nav { display: flex; gap: .25rem; border-bottom: 1px solid var(--border); margin-bottom: 1.5rem; }
  .tab-btn {
    padding: .55rem 1.1rem; background: none; border: none; border-bottom: 2px solid transparent;
    color: var(--muted); cursor: pointer; font-size: .9rem; transition: color .2s, border-color .2s;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* Cards */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.4rem; margin-bottom: 1.2rem; }
  .card h2 { font-size: 1rem; margin-bottom: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }

  /* Radio group */
  .radio-group { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
  .radio-group label { display: flex; align-items: center; gap: .45rem; cursor: pointer; }
  .radio-group input[type=radio] { accent-color: var(--accent); width: 1rem; height: 1rem; }
  .widget-block { display: none; margin-top: 1rem; }
  .widget-block.visible { display: block; }

  /* Inputs */
  input[type=text], input[type=url], select {
    width: 100%; padding: .55rem .75rem; background: var(--surface2); border: 1px solid var(--border);
    border-radius: var(--radius); color: var(--text); font-size: .9rem; outline: none; transition: border-color .2s;
  }
  input[type=text]:focus, input[type=url]:focus, select:focus { border-color: var(--accent); }
  label.field-label { display: block; font-size: .82rem; color: var(--muted); margin-bottom: .35rem; margin-top: .9rem; }

  /* File drop zone */
  .drop-zone {
    border: 2px dashed var(--border); border-radius: var(--radius); padding: 2rem;
    text-align: center; cursor: pointer; transition: border-color .2s, background .2s; position: relative;
  }
  .drop-zone:hover, .drop-zone.dragover { border-color: var(--accent); background: rgba(124,106,255,.06); }
  .drop-zone input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }
  .drop-zone p { color: var(--muted); font-size: .9rem; pointer-events: none; }
  .drop-zone .file-name { color: var(--success); font-size: .85rem; margin-top: .5rem; }

  /* Selects row */
  .select-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }

  /* Video preview */
  #video-preview { width: 100%; border-radius: var(--radius); background: #000; max-height: 360px; display: none; }
  #video-preview.visible { display: block; }
  .no-media-msg { color: var(--muted); font-size: .9rem; padding: 2rem; text-align: center; background: var(--surface2); border-radius: var(--radius); }

  /* Time fields */
  .time-row { display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap; }
  .time-row .time-field { flex: 1; min-width: 140px; }

  /* Handles (range sliders) */
  .handle-row { margin-top: 1rem; display: flex; flex-direction: column; gap: .6rem; }
  .handle-row label { font-size: .82rem; color: var(--muted); }
  input[type=range] { width: 100%; accent-color: var(--accent); }

  /* Buttons */
  .btn {
    display: inline-flex; align-items: center; gap: .4rem;
    padding: .6rem 1.3rem; border: none; border-radius: var(--radius);
    font-size: .9rem; cursor: pointer; transition: opacity .2s, transform .1s; font-family: var(--font);
  }
  .btn:active { transform: scale(.97); }
  .btn:disabled { opacity: .45; cursor: not-allowed; }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: var(--accent2); }
  .btn-danger { background: var(--danger); color: #fff; }
  .btn-sm { padding: .35rem .8rem; font-size: .8rem; }

  /* Progress / status */
  #status-bar { display: none; margin-top: 1rem; padding: .7rem 1rem; border-radius: var(--radius); font-size: .85rem; background: var(--surface2); border-left: 3px solid var(--accent); }
  #status-bar.error { border-left-color: var(--danger); color: var(--danger); }
  #status-bar.success { border-left-color: var(--success); color: var(--success); }

  /* Output list */
  #output-list { list-style: decimal inside; display: flex; flex-direction: column; gap: .6rem; }
  #output-list li { background: var(--surface2); border-radius: var(--radius); padding: .7rem 1rem; display: flex; justify-content: space-between; align-items: center; }
  #output-list li span { font-size: .85rem; color: var(--muted); }
  #zip-section { margin-top: 1.2rem; display: none; }

  /* Spinner */
  .spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite; display: none; }
  .spinner.visible { display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }

  @media (max-width: 600px) {
    main { padding: 1rem; }
    .time-row { flex-direction: column; }
  }
</style>
</head>
<body>

<header><h1>&#9986; Media cutter</h1></header>

<main>
  <div class="tabs-nav">
    <button class="tab-btn active" data-tab="tab-input">1 · Media input</button>
    <button class="tab-btn" data-tab="tab-params">2 · Parameters</button>
    <button class="tab-btn" data-tab="tab-preview">3 · Preview &amp; edit</button>
    <button class="tab-btn" data-tab="tab-output">4 · Output</button>
  </div>

  <!-- TAB 1: Media input -->
  <div id="tab-input" class="tab-panel active">
    <div class="card">
      <h2>Source</h2>
      <div class="radio-group">
        <label><input type="radio" name="source" value="file" id="radio-file" checked/> Upload file</label>
        <label><input type="radio" name="source" value="yt" id="radio-yt"/> YouTube URL</label>
      </div>

      <div id="widget-file" class="widget-block visible">
        <div class="drop-zone" id="drop-zone">
          <p>Drop a video or audio file here, or click to browse</p>
          <p class="file-name" id="file-label"></p>
          <input type="file" id="media-file" accept="video/*,audio/*"/>
        </div>
      </div>

      <div id="widget-yt" class="widget-block">
        <label class="field-label" for="yt-url">YouTube URL</label>
        <input type="url" id="yt-url" placeholder="https://www.youtube.com/watch?v=…"/>
        <small style="color:var(--muted);font-size:.78rem;margin-top:.3rem;display:block;">
          Requires yt-dlp installed on the server.
        </small>
      </div>
    </div>
    <button class="btn btn-primary" onclick="goTab('tab-params')">Next →</button>
  </div>

  <!-- TAB 2: Parameters -->
  <div id="tab-params" class="tab-panel">
    <div class="card">
      <h2>Transcription &amp; model</h2>
      <div class="select-grid">
        <div>
          <label class="field-label" for="sel-engine">Transcription engine</label>
          <select id="sel-engine">
            <option value="whisper">OpenAI Whisper (local)</option>
            <option value="none">None (cut only)</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="sel-lang">Media language</label>
          <select id="sel-lang">
            <option value="auto">Auto-detect</option>
            <option value="en">English</option>
            <option value="fr">French</option>
            <option value="es">Spanish</option>
            <option value="de">German</option>
            <option value="it">Italian</option>
            <option value="pt">Portuguese</option>
            <option value="nl">Dutch</option>
            <option value="pl">Polish</option>
            <option value="ru">Russian</option>
            <option value="zh">Chinese</option>
            <option value="ja">Japanese</option>
            <option value="ar">Arabic</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="sel-model">Whisper model size</label>
          <select id="sel-model">
            <option value="tiny">tiny (fastest)</option>
            <option value="base" selected>base</option>
            <option value="small">small</option>
            <option value="medium">medium</option>
            <option value="large">large (slowest)</option>
          </select>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:.8rem;">
      <button class="btn btn-primary" onclick="goTab('tab-input')">← Back</button>
      <button class="btn btn-primary" onclick="loadPreview()">Load preview →</button>
    </div>
  </div>

  <!-- TAB 3: Preview & edit -->
  <div id="tab-preview" class="tab-panel">
    <div class="card">
      <h2>Preview</h2>
      <div id="no-media-msg" class="no-media-msg">No media loaded yet. Go to tab 1 and select a source.</div>
      <video id="video-preview" controls></video>
    </div>
    <div class="card">
      <h2>Cut points</h2>
      <div class="handle-row">
        <label>Start <span id="lbl-start">0.00 s</span></label>
        <input type="range" id="handle-start" min="0" max="100" step="0.01" value="0"/>
        <label>End <span id="lbl-end">0.00 s</span></label>
        <input type="range" id="handle-end" min="0" max="100" step="0.01" value="100"/>
      </div>
      <div class="time-row">
        <div class="time-field">
          <label class="field-label" for="t-start">Start time (HH:MM:SS or seconds)</label>
          <input type="text" id="t-start" placeholder="00:00:00"/>
        </div>
        <div class="time-field">
          <label class="field-label" for="t-end">End time (HH:MM:SS or seconds)</label>
          <input type="text" id="t-end" placeholder="00:00:00"/>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;">
      <button class="btn btn-primary" onclick="goTab('tab-params')">← Back</button>
      <button class="btn btn-primary" id="btn-cut" onclick="submitCut()">
        <span class="spinner" id="cut-spinner"></span> ✂ Cut &amp; process
      </button>
      <div id="status-bar"></div>
    </div>
  </div>

  <!-- TAB 4: Output -->
  <div id="tab-output" class="tab-panel">
    <div class="card">
      <h2>Output files</h2>
      <ol id="output-list"><li style="color:var(--muted);list-style:none;">No files yet.</li></ol>
      <div id="zip-section">
        <a id="zip-link" class="btn btn-primary" href="#">⬇ Download all as ZIP</a>
      </div>
    </div>
    <button class="btn btn-primary" onclick="goTab('tab-preview')">← Back</button>
  </div>
</main>

<footer>&copy; <span id="yr"></span> Media cutter &mdash; all processing is local</footer>

<script>
// ── Utilities ────────────────────────────────────────────────────────────────
document.getElementById('yr').textContent = new Date().getFullYear();

function goTab(id) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelector('[data-tab="' + id + '"]').classList.add('active');
}
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => goTab(btn.dataset.tab));
});

function parseTime(s) {
  if (!s) return null;
  s = s.trim();
  if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
  const parts = s.split(':').map(Number);
  if (parts.length === 3) return parts[0]*3600 + parts[1]*60 + parts[2];
  if (parts.length === 2) return parts[0]*60 + parts[1];
  return null;
}
function fmtTime(sec) {
  if (isNaN(sec)) return '0.00 s';
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = (sec%60).toFixed(2);
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(Math.floor(s)).padStart(2,'0')}` : `${m}:${String(Math.floor(s)).padStart(2,'0')}.${s.split('.')[1]}`;
}

// ── Source toggle ─────────────────────────────────────────────────────────────
document.querySelectorAll('input[name=source]').forEach(r => {
  r.addEventListener('change', () => {
    document.getElementById('widget-file').classList.toggle('visible', r.value === 'file');
    document.getElementById('widget-yt').classList.toggle('visible', r.value === 'yt');
  });
});

// ── Drop zone ─────────────────────────────────────────────────────────────────
const dz = document.getElementById('drop-zone');
const fileInput = document.getElementById('media-file');
const fileLabel = document.getElementById('file-label');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('dragover');
  if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; updateFileLabel(); }
});
fileInput.addEventListener('change', updateFileLabel);
function updateFileLabel() {
  fileLabel.textContent = fileInput.files[0] ? fileInput.files[0].name : '';
}

// ── Preview ────────────────────────────────────────────────────────────────────
const vid = document.getElementById('video-preview');
const noMsg = document.getElementById('no-media-msg');
let mediaDuration = 0;
let localObjectURL = null;

function loadPreview() {
  const src = document.querySelector('input[name=source]:checked').value;
  if (src === 'file') {
    if (!fileInput.files[0]) { alert('Please select a media file first.'); return; }
    if (localObjectURL) URL.revokeObjectURL(localObjectURL);
    localObjectURL = URL.createObjectURL(fileInput.files[0]);
    vid.src = localObjectURL;
    vid.classList.add('visible');
    noMsg.style.display = 'none';
    vid.onloadedmetadata = () => {
      mediaDuration = vid.duration;
      initHandles(mediaDuration);
    };
  } else {
    noMsg.textContent = 'YouTube preview not available in browser. Duration will be determined after download.';
    noMsg.style.display = 'block';
    vid.classList.remove('visible');
    mediaDuration = 0;
    initHandles(3600);
  }
  goTab('tab-preview');
}

function initHandles(dur) {
  const hs = document.getElementById('handle-start');
  const he = document.getElementById('handle-end');
  hs.max = dur; hs.value = 0;
  he.max = dur; he.value = dur;
  document.getElementById('lbl-start').textContent = fmtTime(0);
  document.getElementById('lbl-end').textContent = fmtTime(dur);
  document.getElementById('t-start').value = '00:00:00';
  document.getElementById('t-end').value = fmtTime(dur);
}

document.getElementById('handle-start').addEventListener('input', function() {
  document.getElementById('lbl-start').textContent = fmtTime(+this.value);
  document.getElementById('t-start').value = fmtTime(+this.value);
  if (+this.value > +document.getElementById('handle-end').value)
    document.getElementById('handle-end').value = this.value;
});
document.getElementById('handle-end').addEventListener('input', function() {
  document.getElementById('lbl-end').textContent = fmtTime(+this.value);
  document.getElementById('t-end').value = fmtTime(+this.value);
  if (+this.value < +document.getElementById('handle-start').value)
    document.getElementById('handle-start').value = this.value;
});
document.getElementById('t-start').addEventListener('change', function() {
  const v = parseTime(this.value);
  if (v !== null) { document.getElementById('handle-start').value = v; document.getElementById('lbl-start').textContent = fmtTime(v); }
});
document.getElementById('t-end').addEventListener('change', function() {
  const v = parseTime(this.value);
  if (v !== null) { document.getElementById('handle-end').value = v; document.getElementById('lbl-end').textContent = fmtTime(v); }
});

// ── Submit cut ────────────────────────────────────────────────────────────────
async function submitCut() {
  const statusBar = document.getElementById('status-bar');
  const spinner = document.getElementById('cut-spinner');
  const btn = document.getElementById('btn-cut');

  const startVal = parseTime(document.getElementById('t-start').value);
  const endVal   = parseTime(document.getElementById('t-end').value);
  if (startVal === null || endVal === null || endVal <= startVal) {
    showStatus('Invalid start/end times.', 'error'); return;
  }

  const fd = new FormData();
  const src = document.querySelector('input[name=source]:checked').value;
  fd.append('source', src);
  if (src === 'file') {
    if (!fileInput.files[0]) { showStatus('No file selected.', 'error'); return; }
    fd.append('media_file', fileInput.files[0]);
  } else {
    const url = document.getElementById('yt-url').value.trim();
    if (!url) { showStatus('No YouTube URL entered.', 'error'); return; }
    fd.append('yt_url', url);
  }
  fd.append('start', startVal);
  fd.append('end', endVal);
  fd.append('engine', document.getElementById('sel-engine').value);
  fd.append('lang', document.getElementById('sel-lang').value);
  fd.append('model', document.getElementById('sel-model').value);

  btn.disabled = true; spinner.classList.add('visible');
  showStatus('Processing… this may take a while.', '');

  try {
    const resp = await fetch('/cut', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) { showStatus(data.error || 'Server error.', 'error'); return; }
    showStatus('Done!', 'success');
    renderOutputs(data.files, data.zip);
    goTab('tab-output');
  } catch(e) {
    showStatus('Network error: ' + e.message, 'error');
  } finally {
    btn.disabled = false; spinner.classList.remove('visible');
  }
}

function showStatus(msg, cls) {
  const sb = document.getElementById('status-bar');
  sb.textContent = msg; sb.style.display = 'block';
  sb.className = cls ? 'error' === cls ? 'error' : cls : '';
  sb.style.display = msg ? 'block' : 'none';
}

function renderOutputs(files, zip) {
  const ol = document.getElementById('output-list');
  ol.innerHTML = '';
  if (!files || !files.length) { ol.innerHTML = '<li style="color:var(--muted);list-style:none;">No files produced.</li>'; return; }
  files.forEach(f => {
    const li = document.createElement('li');
    li.innerHTML = `<span>${f.name}</span><a class="btn btn-primary btn-sm" href="${f.url}" download="${f.name}">⬇ Download</a>`;
    ol.appendChild(li);
  });
  const zs = document.getElementById('zip-section');
  if (zip) { zs.style.display = 'block'; document.getElementById('zip-link').href = zip; }
  else { zs.style.display = 'none'; }
}
</script>
</body>
</html>
"""

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return HTML

@app.route('/cut', methods=['POST'])
def cut():
    import subprocess, shutil

    source  = request.form.get('source', 'file')
    start   = request.form.get('start', '0')
    end     = request.form.get('end', '0')
    engine  = request.form.get('engine', 'none')
    lang    = request.form.get('lang', 'auto')
    model   = request.form.get('model', 'base')

    try:
        start_sec = float(start)
        end_sec   = float(end)
    except ValueError:
        return jsonify({'error': 'Invalid time values.'}), 400

    if end_sec <= start_sec:
        return jsonify({'error': 'End time must be after start time.'}), 400

    job_id  = uuid.uuid4().hex
    job_dir = UPLOAD_FOLDER / job_id
    job_dir.mkdir()

    try:
        # ── Obtain input file ─────────────────────────────────────────────────
        if source == 'file':
            f = request.files.get('media_file')
            if not f:
                return jsonify({'error': 'No file uploaded.'}), 400
            original_name = Path(f.filename).name
            # Sanitise filename
            safe_name = ''.join(c if c.isalnum() or c in '._- ' else '_' for c in original_name)
            input_path = job_dir / ('input_' + safe_name)
            f.save(str(input_path))
        else:
            yt_url = request.form.get('yt_url', '').strip()
            if not yt_url.startswith(('https://www.youtube.com/', 'https://youtu.be/',
                                       'https://youtube.com/', 'http://www.youtube.com/')):
                return jsonify({'error': 'Invalid YouTube URL.'}), 400
            if not shutil.which('yt-dlp'):
                return jsonify({'error': 'yt-dlp is not installed on the server.'}), 500
            input_path = job_dir / 'input_yt.%(ext)s'
            dl_result = subprocess.run(
                ['yt-dlp', '--no-playlist', '-o', str(input_path), yt_url],
                capture_output=True, text=True, timeout=300
            )
            if dl_result.returncode != 0:
                return jsonify({'error': 'yt-dlp failed: ' + dl_result.stderr[:300]}), 500
            candidates = list(job_dir.glob('input_yt.*'))
            if not candidates:
                return jsonify({'error': 'yt-dlp produced no output file.'}), 500
            input_path = candidates[0]

        if not input_path.exists():
            return jsonify({'error': 'Input file missing after download.'}), 500

        # ── Determine suffix ──────────────────────────────────────────────────
        in_suffix = input_path.suffix.lower() or '.mp4'
        cut_path  = job_dir / ('cut' + in_suffix)

        # ── Run ffmpeg to cut ─────────────────────────────────────────────────
        if not shutil.which('ffmpeg'):
            return jsonify({'error': 'ffmpeg is not installed on the server.'}), 500

        duration = end_sec - start_sec
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_sec),
            '-i', str(input_path),
            '-t', str(duration),
            '-c', 'copy',
            str(cut_path)
        ]
        ff = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)
        if ff.returncode != 0:
            return jsonify({'error': 'ffmpeg failed: ' + ff.stderr[-500:]}), 500

        produced_files = [cut_path]

        # ── Optional transcription ────────────────────────────────────────────
        transcript_path = None
        if engine == 'whisper':
            try:
                import whisper as _whisper
                wmodel = _whisper.load_model(model)
                w_kwargs = {} if lang == 'auto' else {'language': lang}
                result  = wmodel.transcribe(str(cut_path), **w_kwargs)
                transcript_path = job_dir / 'transcript.txt'
                with open(transcript_path, 'w', encoding='utf-8') as tf:
                    tf.write(result.get('text', ''))
                produced_files.append(transcript_path)

                # Also write SRT
                srt_path = job_dir / 'transcript.srt'
                segments = result.get('segments', [])
                with open(srt_path, 'w', encoding='utf-8') as sf:
                    for i, seg in enumerate(segments, 1):
                        sf.write(f"{i}\n")
                        sf.write(_srt_ts(seg['start']) + ' --> ' + _srt_ts(seg['end']) + '\n')
                        sf.write(seg['text'].strip() + '\n\n')
                produced_files.append(srt_path)
            except ImportError:
                pass  # whisper not installed; skip silently
            except Exception as we:
                pass  # transcription failed; still return cut file

        # ── Build ZIP ─────────────────────────────────────────────────────────
        zip_path = job_dir / 'output.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in produced_files:
                if p.exists():
                    zf.write(p, p.name)

        # ── Build response ────────────────────────────────────────────────────
        files_resp = []
        for p in produced_files:
            if p.exists():
                files_resp.append({'name': p.name, 'url': f'/download/{job_id}/{p.name}'})

        return jsonify({
            'files': files_resp,
            'zip':   f'/download/{job_id}/output.zip'
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Processing timed out.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _srt_ts(seconds):
    ms  = int((seconds % 1) * 1000)
    s   = int(seconds) % 60
    m   = (int(seconds) // 60) % 60
    h   = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@app.route('/download/<job_id>/<filename>')
def download(job_id, filename):
    # Strict path validation
    if not job_id.isalnum() or len(job_id) != 32:
        return 'Not found', 404
    safe_filename = Path(filename).name
    file_path = UPLOAD_FOLDER / job_id / safe_filename
    resolved  = file_path.resolve()
    base      = UPLOAD_FOLDER.resolve()
    if not str(resolved).startswith(str(base)):
        return 'Forbidden', 403
    if not resolved.exists():
        return 'Not found', 404
    return send_file(str(resolved), as_attachment=True, download_name=safe_filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5045, debug=False)
