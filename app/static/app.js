const form = document.querySelector("#analyzeForm");
const statusPill = document.querySelector("#statusPill");
const emptyState = document.querySelector("#emptyState");
const summary = document.querySelector("#videoSummary");
const clipList = document.querySelector("#clipList");
const renderOutput = document.querySelector("#renderOutput");
const renderTop5 = document.querySelector("#renderTop5");
const renderNext5 = document.querySelector("#renderNext5");

let lastRequest = null;
let lastAnalysis = null;
let activeJobTimer = null;
let analysisTimer = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  lastRequest = readRequest();
  await analyzeAndRender(lastRequest);
});

renderTop5.addEventListener("click", () => renderBatch(1, 5));
renderNext5.addEventListener("click", () => renderBatch(6, 5));

const savedJobId = localStorage.getItem("activeRenderJobId");
if (savedJobId) {
  emptyState.classList.add("hidden");
  setStatus("Reconnecting", "busy");
  renderOutput.classList.remove("hidden");
  renderOutput.innerHTML = renderJobShell("Reconnecting to render", 0, Number(document.querySelector("#maxClips").value));
  pollRenderJob(savedJobId);
}

function readRequest() {
  return {
    youtube_url: document.querySelector("#youtubeUrl").value.trim(),
    max_clips: Number(document.querySelector("#maxClips").value),
    min_duration_sec: Number(document.querySelector("#minDuration").value),
    max_duration_sec: Number(document.querySelector("#maxDuration").value),
  };
}

async function analyzeAndRender(payload) {
  setStatus("Starting", "busy");
  emptyState.classList.add("hidden");
  renderOutput.classList.add("hidden");
  summary.classList.add("hidden");
  clipList.innerHTML = "";
  renderTop5.disabled = true;
  renderNext5.disabled = true;
  try {
    const speed = Number(document.querySelector("#speed").value);
    renderOutput.classList.remove("hidden");
    renderOutput.innerHTML = renderJobShell("Queued", 0, payload.max_clips);
    const job = await postJson("/render", {
      ...payload,
      start_rank: 1,
      max_clips: payload.max_clips,
      speed,
      target_rank: null,
    });
    pollRenderJob(job.id);
  } catch (error) {
    setStatus("Error", "error");
    showError(error.message);
  }
}

async function renderBatch(startRank, maxClips) {
  startRenderJob({ startRank, maxClips });
}

async function renderSingle(rank) {
  startRenderJob({ startRank: rank, maxClips: 1, targetRank: rank });
}

async function startRenderJob({ startRank, maxClips, targetRank = null }) {
  if (!lastRequest) return;
  setStatus("Starting render", "busy");
  renderOutput.classList.remove("hidden");
  renderOutput.innerHTML = renderJobShell("Creating job", 0, maxClips);
  try {
    const speed = Number(document.querySelector("#speed").value);
    const job = await postJson("/render", {
      ...lastRequest,
      start_rank: startRank,
      max_clips: maxClips,
      speed,
      target_rank: targetRank,
    });
    localStorage.setItem("activeRenderJobId", job.id);
    pollRenderJob(job.id);
  } catch (error) {
    setStatus("Render error", "error");
    showError(error.message);
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function renderAnalysis(data) {
  emptyState.classList.add("hidden");
  summary.classList.remove("hidden");
  summary.innerHTML = `
    <div class="video-title">
      <div class="metric-label">Video</div>
      <h2>${escapeHtml(data.video.title)}</h2>
    </div>
    ${metric("Views", formatNumber(data.video.view_count))}
    ${metric("Likes", formatNumber(data.video.like_count))}
    ${metric("Comments", formatNumber(data.video.comment_count))}
  `;

  clipList.innerHTML = data.clips.map(renderClipCard).join("");
}

function metric(label, value) {
  return `
    <div class="metric">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
    </div>
  `;
}

function renderClipCard(clip) {
  const evidence = (clip.comment_evidence || []).slice(0, 2).map(escapeHtml).join("<br>");
  return `
    <article class="clip-card">
      <div class="rank">#${clip.rank}</div>
      <div>
        <div class="clip-title">${escapeHtml(clip.title)}</div>
        <div class="clip-hook">${escapeHtml(clip.hook)}</div>
        <div class="clip-reason">${escapeHtml(clip.reason)}</div>
        ${evidence ? `<div class="evidence">${evidence}</div>` : ""}
      </div>
      <div class="score">
        <div class="score-number">${clip.score}</div>
        <div class="metric-label">viral score</div>
        <div class="time">${formatTime(clip.start_sec)} - ${formatTime(clip.end_sec)}</div>
        <button class="mini-action" type="button" onclick="renderSingle(${clip.rank})">Render</button>
      </div>
    </article>
  `;
}

function startAnalysisProgress() {
  emptyState.classList.add("hidden");
  renderOutput.classList.add("hidden");
  let pct = 8;
  clipList.innerHTML = `
    <section class="analysis-progress">
      <div class="job-head">
        <div>
          <h2>Analyzing video</h2>
          <p id="analysisPhase">Reading video metadata and comments</p>
        </div>
        <div id="analysisPercent" class="job-percent">8%</div>
      </div>
      <div class="progress-track"><div id="analysisFill" class="progress-fill" style="width:8%"></div></div>
      <div class="analysis-steps">
        <span>Metadata</span>
        <span>Transcript</span>
        <span>Comments</span>
        <span>Gemini score</span>
      </div>
    </section>
  `;
  const phases = [
    "Reading video metadata and comments",
    "Fetching transcript timing",
    "Finding candidate moments",
    "Scoring viral hooks with Gemini",
  ];
  let phaseIndex = 0;
  analysisTimer = setInterval(() => {
    pct = Math.min(92, pct + 7);
    phaseIndex = Math.min(phases.length - 1, Math.floor(pct / 25));
    document.querySelector("#analysisFill").style.width = `${pct}%`;
    document.querySelector("#analysisPercent").textContent = `${pct}%`;
    document.querySelector("#analysisPhase").textContent = phases[phaseIndex];
  }, 850);
}

function stopAnalysisProgress() {
  if (analysisTimer) {
    clearInterval(analysisTimer);
    analysisTimer = null;
  }
}

function pollRenderJob(jobId) {
  if (activeJobTimer) {
    clearInterval(activeJobTimer);
  }

  const refresh = async () => {
    try {
      const response = await fetch(`/render/jobs/${jobId}`);
      const job = await response.json();
      if (!response.ok) {
        throw new Error(job.detail || "Could not read render job");
      }
      showRenderJob(job);
      if (job.status === "completed") {
        clearInterval(activeJobTimer);
        activeJobTimer = null;
        localStorage.removeItem("activeRenderJobId");
        setStatus("Render ready", "");
      }
      if (job.status === "failed") {
        clearInterval(activeJobTimer);
        activeJobTimer = null;
        localStorage.removeItem("activeRenderJobId");
        setStatus("Render failed", "error");
      }
    } catch (error) {
      clearInterval(activeJobTimer);
      activeJobTimer = null;
      localStorage.removeItem("activeRenderJobId");
      setStatus("Render error", "error");
      showError(error.message);
    }
  };

  refresh();
  activeJobTimer = setInterval(refresh, 2500);
}

function showRenderJob(job) {
  renderOutput.classList.remove("hidden");
  renderOutput.innerHTML = renderJobShell(job.phase, job.progress, job.total, job.status, job.error);
  const gallery = renderOutput.querySelector(".preview-grid");
  const files = job.files || [];
  const clips = job.clips || [];
  gallery.innerHTML = files.map((file, index) => renderPreviewCard(file, clips[index], index)).join("");
  if (files.length > 0) {
    emptyState.classList.add("hidden");
  }
}

function renderJobShell(phase, progress, total, status = "running", error = null) {
  const pct = jobPercent(phase, progress, total, status);
  return `
    <div class="job-head">
      <div>
        <h2>${escapeHtml(phase)}</h2>
        <p>${status === "failed" ? escapeHtml(error || "Render failed") : `${progress}/${total} clips ready`}</p>
      </div>
      <div class="job-percent">${pct}%</div>
    </div>
    <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
    <div class="preview-grid"></div>
  `;
}

function jobPercent(phase, progress, total, status) {
  if (status === "completed") return 100;
  if (status === "failed") return 100;
  const normalized = String(phase || "").toLowerCase();
  if (normalized.includes("queued")) return 3;
  if (normalized.includes("analyzing")) return 12;
  if (normalized.includes("downloading")) return 22;
  if (normalized.includes("rendering")) {
    const renderPct = total > 0 ? progress / total : 0;
    return Math.max(28, Math.min(98, Math.round(28 + renderPct * 70)));
  }
  return total > 0 ? Math.round((progress / total) * 100) : 0;
}

function renderPreviewCard(file, clip, index) {
  const url = `/files?path=${encodeURIComponent(file)}`;
  const title = clip?.title || `Clip ${index + 1}`;
  const rank = clip?.rank || index + 1;
  const score = clip?.score ? `${clip.score} score` : "Rendered";
  return `
    <article class="preview-card">
      <video controls preload="metadata" src="${url}"></video>
      <div class="preview-meta">
        <div>
          <div class="preview-title">#${rank} ${escapeHtml(title)}</div>
          <div class="metric-label">${escapeHtml(score)}</div>
        </div>
        <div class="preview-actions">
          <a href="${url}" target="_blank">Open</a>
          <a href="${url}" download>Download</a>
        </div>
      </div>
    </article>
  `;
}

function showRenderOutput(files) {
  renderOutput.classList.remove("hidden");
  renderOutput.innerHTML = `
    <h2>Rendered files</h2>
    ${files.map((file) => `<a href="/files?path=${encodeURIComponent(file)}" target="_blank">${escapeHtml(file)}</a>`).join("")}
  `;
}

function showError(message) {
  emptyState.classList.add("hidden");
  summary.classList.add("hidden");
  clipList.innerHTML = `
    <article class="clip-card">
      <div class="rank">!</div>
      <div>
        <div class="clip-title">Something needs attention</div>
        <div class="clip-reason">${escapeHtml(message)}</div>
      </div>
    </article>
  `;
}

function setStatus(text, type) {
  statusPill.textContent = text;
  statusPill.className = `status ${type || ""}`;
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(Math.floor(totalSeconds % 60)).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
