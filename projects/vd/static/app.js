const state = {
  mediaId: null,
  duration: 0,
  filename: null,
};

const el = (id) => document.getElementById(id);
const statusEl = el("status");

function setStatus(msg, isError = false) {
  statusEl.textContent = msg || "";
  statusEl.style.color = isError ? "#ff6b6b" : "#4ade80";
}

// --- tabs ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    el(`tab-${btn.dataset.tab}`).classList.remove("hidden");
  });
});

// --- loading media ---
async function onMediaLoaded(data) {
  state.mediaId = data.id;
  state.duration = data.duration;
  state.filename = data.filename || null;

  const video = el("preview");
  video.src = data.url;
  el("videoSection").classList.remove("hidden");
  
  if (state.filename) {
    el("fileInfo").textContent = `File: ${state.filename}`;
  }
}

el("loadYoutubeBtn").addEventListener("click", async () => {
  const url = el("youtubeUrl").value.trim();
  if (!url) return setStatus("Enter a YouTube URL.", true);
  setStatus("Downloading video...");
  el("loadYoutubeBtn").disabled = true;
  try {
    const res = await fetch("/api/youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, use_chrome_cookies: el("useCookies").checked }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load video.");
    await onMediaLoaded(data);
    setStatus("Video loaded successfully!");
  } catch (e) {
    setStatus(e.message, true);
  } finally {
    el("loadYoutubeBtn").disabled = false;
  }
});

el("fileInput").addEventListener("change", async () => {
  const file = el("fileInput").files[0];
  if (!file) return;
  setStatus("Uploading video...");
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed.");
    await onMediaLoaded(data);
    setStatus("Video loaded successfully!");
  } catch (e) {
    setStatus(e.message, true);
  }
});

// --- download ---
el("downloadBtn").addEventListener("click", () => {
  if (state.mediaId) {
    window.location = `/api/download/${state.mediaId}`;
  }
});
