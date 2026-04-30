const form = document.querySelector("#analyzeForm");
const statusPill = document.querySelector("#statusPill");
const emptyState = document.querySelector("#emptyState");
const summary = document.querySelector("#videoSummary");
const clipList = document.querySelector("#clipList");
const renderOutput = document.querySelector("#renderOutput");
const geminiApiKey = document.querySelector("#geminiApiKey");
const youtubeApiKey = document.querySelector("#youtubeApiKey");
const authPanel = document.querySelector("#authPanel");
const signedOutAuth = document.querySelector("#signedOutAuth");
const signedInAuth = document.querySelector("#signedInAuth");
const authEmail = document.querySelector("#authEmail");
const authUserEmail = document.querySelector("#authUserEmail");
const dailyLimitText = document.querySelector("#dailyLimitText");
const sendMagicLink = document.querySelector("#sendMagicLink");
const signOut = document.querySelector("#signOut");
const advancedToggle = document.querySelector("#advancedToggle");
const advancedSettings = document.querySelector("#advancedSettings");

let lastRequest = null;
let activeJobTimer = null;
let appConfig = { auth_required: false };
let supabaseClient = null;
let authSession = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  lastRequest = readRequest();
  await analyzeAndRender(lastRequest);
});

advancedToggle.addEventListener("click", () => {
  advancedSettings.classList.toggle("hidden");
});

initApp();

function readRequest() {
  return {
    youtube_url: document.querySelector("#youtubeUrl").value.trim(),
    max_clips: Number(document.querySelector("#maxClips").value),
    min_duration_sec: Number(document.querySelector("#minDuration").value),
    max_duration_sec: Number(document.querySelector("#maxDuration").value),
    gemini_api_key: geminiApiKey.value.trim() || null,
    youtube_api_key: youtubeApiKey.value.trim() || null,
  };
}

async function initApp() {
  try {
    appConfig = await fetch("/app-config").then((r) => r.json());
    if (appConfig.auth_required) {
      authPanel.classList.remove("hidden");
      supabaseClient = window.supabase.createClient(appConfig.supabase_url, appConfig.supabase_anon_key);
      const { data } = await supabaseClient.auth.getSession();
      authSession = data.session;
      renderAuthState();
    }
  } catch (e) { console.error(e); }
}

function renderAuthState() {
  const user = authSession?.user;
  if (user) {
    signedOutAuth.classList.add("hidden");
    signedInAuth.classList.remove("hidden");
    authUserEmail.textContent = user.email;
  }
}

async function analyzeAndRender(payload) {
  setStatus("Analyzing...", "busy");
  emptyState.innerHTML = `<div class="editorial-divider"></div><p>Intelligence in progress. <br>Scanning for viral hooks and high-impact payoffs...</p>`;
  
  try {
    const speed = Number(document.querySelector("#speed").value);
    const job = await postJson("/render", { ...payload, start_rank: 1, speed });
    pollRenderJob(job.id);
  } catch (error) {
    showError(error.message);
  }
}

async function renderSingle(rank) {
  if (!lastRequest) return;
  const speed = Number(document.querySelector("#speed").value);
  const job = await postJson("/render", { ...lastRequest, start_rank: rank, max_clips: 1, target_rank: rank, speed });
  pollRenderJob(job.id);
}

async function postJson(url, payload) {
  const headers = { "Content-Type": "application/json" };
  if (authSession?.access_token) headers.Authorization = `Bearer ${authSession.access_token}`;
  const response = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function pollRenderJob(jobId) {
  if (activeJobTimer) clearInterval(activeJobTimer);
  activeJobTimer = setInterval(async () => {
    const job = await fetch(`/render/jobs/${jobId}`).then(r => r.json());
    showRenderJob(job);
    if (job.status === "completed" || job.status === "failed") clearInterval(activeJobTimer);
  }, 2500);
}

function showRenderJob(job) {
  if (job.clips && job.clips.length > 0 && clipList.innerHTML === "") {
    renderAnalysis({ video: { title: "Analyzed Content" }, clips: job.clips });
  }
  renderOutput.classList.remove("hidden");
  renderOutput.innerHTML = `
    <div class="job-card">
      <div class="job-head">
        <div class="clip-byline">${job.phase}</div>
        <h2>${job.status === "completed" ? "Manifest Complete" : "Processing Stream"}</h2>
      </div>
      <div class="progress-bar-minimal"><div class="progress-fill-ink" style="width: ${jobPercent(job)}%"></div></div>
      <div class="preview-feed">
        ${(job.files || []).map((file, i) => `
          <div class="preview-item">
            <video controls src="/files?path=${encodeURIComponent(file)}"></video>
            <div style="padding: 20px; background: white; border: 1px solid var(--border); border-top:none; border-radius: 0 0 24px 24px;">
               <div class="clip-byline">Ready to Broadcast</div>
               <a href="/files?path=${encodeURIComponent(file)}" download class="text-btn">Download Asset</a>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function jobPercent(job) {
  if (job.status === "completed") return 100;
  return Math.max(5, (job.progress / (job.total || 1)) * 100);
}

function renderAnalysis(data) {
  emptyState.classList.add("hidden");
  summary.classList.remove("hidden");
  summary.innerHTML = `<h2>${escapeHtml(data.video.title)}</h2>`;
  clipList.innerHTML = data.clips.map(renderClipCard).join("");
}

function renderClipCard(clip) {
  return `
    <article class="clip-card">
      <div class="clip-byline">Analysis Rank 0${clip.rank} / ViralAI</div>
      <div class="clip-title">${escapeHtml(clip.title)}</div>
      <div class="clip-hook">"${escapeHtml(clip.hook)}"</div>
      <div class="clip-reason">${escapeHtml(clip.reason)}</div>
      <div class="card-footer">
        <div class="viral-metric">
          <div class="clip-byline">Viral Index</div>
          <div class="metric-score">${clip.score}</div>
        </div>
        <button class="render-btn-pilled" onclick="renderSingle(${clip.rank})">Render Perspective</button>
      </div>
    </article>
  `;
}

function setStatus(text) {
  statusPill.textContent = text;
}

function showError(msg) {
  clipList.innerHTML = `<div class="clip-card" style="border-color: var(--danger);"><div class="clip-title">System Error</div><p>${escapeHtml(msg)}</p></div>`;
}

function escapeHtml(v) {
  return String(v || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function formatTime(s) {
  const m = Math.floor(s / 60);
  const sec = String(Math.floor(s % 60)).padStart(2, "0");
  return `${m}:${sec}`;
}
