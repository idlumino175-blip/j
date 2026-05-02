// Pure Stitch AI Implementation: 100% Fidelity Rebuild
const analyzeForm = document.querySelector("#analyzeForm");
const youtubeUrlInput = document.querySelector("#youtubeUrl");
const landingPhase = document.querySelector("#landingPhase");
const forgePhase = document.querySelector("#forgePhase");
const selectionPhase = document.querySelector("#selectionPhase");
const resultPhase = document.querySelector("#resultPhase");

const urlPreview = document.querySelector("#urlPreview");
const previewTitle = document.querySelector("#previewTitle");
const previewThumb = document.querySelector("#previewThumb img");
const previewChannel = document.querySelector("#previewChannel");

const clipList = document.querySelector("#clipList");
const renderOutput = document.querySelector("#renderOutput");
const forgeProgressCircle = document.querySelector("#forgeProgressCircle");
const forgePercentText = document.querySelector("#forgePercentText");
const forgeStatusLabel = document.querySelector("#forgeStatusLabel");
const forgeSteps = document.querySelector("#forgeSteps");
const momentsCountText = document.querySelector("#momentsCountText");

const authBtnNav = document.querySelector("#authBtn");
const signOutBtn = document.querySelector("#signOutBtn");
const userEmailDisplay = document.querySelector("#userEmailDisplay");
const authOverlay = document.querySelector("#authOverlay");
const closeAuth = document.querySelector("#closeAuth");
const signInBtn = document.querySelector("#signInBtn");
const signUpBtn = document.querySelector("#signUpBtn");

const generateSelectedBtn = document.querySelector("#generateSelected");
const cancelForgeBtn = document.querySelector("#cancelForgeBtn");

let lastRequest = null;
let activeJobTimer = null;
let currentJobId = null;
let firebaseUser = null;
let youtubeApiKey = null;
let fluidProgressVal = 0;
let fluidProgressInterval = null;

// UI Toggles
authBtnNav?.addEventListener("click", () => authOverlay.classList.remove("hidden"));
closeAuth?.addEventListener("click", () => authOverlay.classList.add("hidden"));

cancelForgeBtn?.addEventListener("click", async () => {
    if (!currentJobId) return;
    if (confirm("Are you sure you want to cancel? This will stop the AI process immediately.")) {
        try {
            await postJson(`/render/jobs/${currentJobId}/cancel`, {});
            if (activeJobTimer) clearInterval(activeJobTimer);
            currentJobId = null;
            showPhase("landing");
        } catch (e) { showPhase("landing"); }
    }
});

function setSpeed(val) {
    document.querySelector("#speed").value = val;
    document.querySelectorAll(".speed-pill").forEach(btn => {
        const btnVal = parseFloat(btn.textContent);
        if (btnVal === val) {
            btn.classList.add("bg-primary", "text-white", "border-primary");
            btn.classList.remove("border-transparent", "hover:bg-white");
        } else {
            btn.classList.remove("bg-primary", "text-white", "border-primary");
            btn.classList.add("border-transparent", "hover:bg-white");
        }
    });
}

// Live YouTube Preview
youtubeUrlInput?.addEventListener("input", async (e) => {
    const url = e.target.value.trim();
    const videoId = extractVideoId(url);
    if (videoId && youtubeApiKey) {
        urlPreview.classList.remove("hidden");
        previewTitle.textContent = "Fetching video details...";
        try {
            const resp = await fetch(`https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${videoId}&key=${youtubeApiKey}`);
            const data = await resp.json();
            if (data.items && data.items.length > 0) {
                const snip = data.items[0].snippet;
                previewTitle.textContent = snip.title;
                previewThumb.src = snip.thumbnails.medium.url;
                previewChannel.textContent = snip.channelTitle;
            }
        } catch (err) { console.error(err); }
    } else {
        urlPreview.classList.add("hidden");
    }
});

function extractVideoId(url) {
    const regExp = /^.*(youtu\.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

// Firebase
document.addEventListener("DOMContentLoaded", () => {
  fetch("/app-config").then(r => r.json()).then(config => {
    youtubeApiKey = config.youtube_api_key;
    if (!config.auth_enabled) return;
    firebase.initializeApp(config.firebase_config);
    firebase.auth().onAuthStateChanged(user => {
      firebaseUser = user;
      if (user) {
        authOverlay.classList.add("hidden");
        authBtnNav?.classList.add("hidden");
        if (userEmailDisplay) { userEmailDisplay.textContent = user.email; userEmailDisplay.classList.remove("hidden"); }
        signOutBtn?.classList.remove("hidden");
      } else {
        userEmailDisplay?.classList.add("hidden");
        signOutBtn?.classList.add("hidden");
        authBtnNav?.classList.remove("hidden");
      }
    });
  });
});

signInBtn?.addEventListener("click", async () => {
  const email = document.querySelector("#authEmail").value;
  const pass = document.querySelector("#authPassword").value;
  try { await firebase.auth().signInWithEmailAndPassword(email, pass); } 
  catch (e) { document.querySelector("#authMessage").textContent = e.message; }
});

signUpBtn?.addEventListener("click", async () => {
  const email = document.querySelector("#authEmail").value;
  const pass = document.querySelector("#authPassword").value;
  try { await firebase.auth().createUserWithEmailAndPassword(email, pass); } 
  catch (e) { document.querySelector("#authMessage").textContent = e.message; }
});

signOutBtn?.addEventListener("click", () => firebase.auth().signOut());

// Submission
analyzeForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    youtube_url: youtubeUrlInput.value,
    max_clips: Number(document.querySelector("#maxClips")?.value || 10),
    min_duration_sec: 20,
    max_duration_sec: 75,
    speed: Number(document.querySelector("#speed")?.value || 1.1),
    style: "black-box",
  };
  lastRequest = payload;
  showPhase("forge");
  updateForge(5, "Initializing AI Engine...");
  if (forgeSteps) forgeSteps.innerHTML = "";
  try {
    const job = await postJson("/render", { ...payload, start_rank: 1 });
    currentJobId = job.id;
    pollRenderJob(job.id);
  } catch (error) { alert(error.message); showPhase("landing"); }
});

generateSelectedBtn?.addEventListener("click", async () => {
    const checked = Array.from(document.querySelectorAll(".clip-checkbox:checked")).map(cb => Number(cb.value));
    if (checked.length === 0) return;
    showPhase("forge");
    updateForge(5, "Forging selected moments...");
    if (forgeSteps) forgeSteps.innerHTML = "";
    try {
        const job = await postJson("/render", { ...lastRequest, start_rank: checked[0], max_clips: checked.length });
        currentJobId = job.id;
        pollRenderJob(job.id);
    } catch (e) { alert(e.message); showPhase("selection"); }
});

async function postJson(url, payload) {
  const headers = { "Content-Type": "application/json" };
  if (firebaseUser) {
    const token = await firebaseUser.getIdToken();
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function pollRenderJob(jobId) {
  if (activeJobTimer) clearInterval(activeJobTimer);
  activeJobTimer = setInterval(async () => {
    const job = await fetch(`/render/jobs/${jobId}`).then(r => r.json());
    if (job.status === "cancelled") { clearInterval(activeJobTimer); showPhase("landing"); return; }
    
    if (job.phase === "analyzing") {
        updateForge(jobPercent(job), "Analyzing narrative nodes...");
        addForgeStep("Downloading video", "done");
        addForgeStep("Extracting viral moments", "active");
    } else if (job.phase === "rendering") {
        updateForge(jobPercent(job), `Forging clip ${job.current} of ${job.total}...`);
        addForgeStep("Extracting viral moments", "done");
        addForgeStep("Centering for vertical view", "active");
    }

    if (job.status === "completed") {
        clearInterval(activeJobTimer);
        if (job.phase === "analyzing") { showSelection(job.clips); } 
        else { showFinalResults(job.files); }
    } else if (job.status === "failed") {
        clearInterval(activeJobTimer);
        alert(job.error || "Forging failed.");
        showPhase("landing");
    }
  }, 2000);
}

function showPhase(name) {
    [landingPhase, forgePhase, selectionPhase, resultPhase].forEach(p => p.classList.add("hidden"));
    if (name === "landing") { landingPhase.classList.remove("hidden"); stopFluidProgress(); }
    if (name === "forge") { forgePhase.classList.remove("hidden"); startFluidProgress(); }
    if (name === "selection") { selectionPhase.classList.remove("hidden"); stopFluidProgress(); }
    if (name === "result") { resultPhase.classList.remove("hidden"); stopFluidProgress(); }
    window.scrollTo(0, 0);
}

function startFluidProgress() {
    fluidProgressVal = 5;
    if (fluidProgressInterval) clearInterval(fluidProgressInterval);
    const actions = ["Vectorizing Transcript", "Scoring Hook Velocity", "Clustering Metadata", "Analyzing Sentiment", "Mapping Narrative Nodes"];
    let actionIdx = 0;
    fluidProgressInterval = setInterval(() => {
        if (fluidProgressVal < 98) {
            fluidProgressVal += (Math.random() * 0.4);
            updateForge(Math.floor(fluidProgressVal), actions[actionIdx]);
        }
        if (Math.random() > 0.95) actionIdx = (actionIdx + 1) % actions.length;
    }, 400);
}

function stopFluidProgress() {
    if (fluidProgressInterval) clearInterval(fluidProgressInterval);
    fluidProgressInterval = null;
}

function updateForge(percent, label) {
    const offset = 754 - (754 * percent / 100);
    if (forgeProgressCircle) forgeProgressCircle.style.strokeDashoffset = offset;
    if (forgePercentText) forgePercentText.textContent = `${percent}%`;
    const actionLabel = document.querySelector("#forgeActionLabel");
    if (actionLabel && label) actionLabel.textContent = label;
}

function addForgeStep(text, status) {
    const existing = Array.from(forgeSteps.querySelectorAll("p")).find(p => p.textContent === text);
    if (existing) {
        if (status === 'done') {
            const parent = existing.closest('.flex');
            const iconBox = parent.querySelector('.w-9');
            if (iconBox) {
                iconBox.classList.remove('bg-secondary-container', 'text-secondary');
                iconBox.classList.add('bg-secondary', 'text-white');
                iconBox.querySelector('.material-symbols-outlined').textContent = 'check';
            }
        }
        return;
    }
    const div = document.createElement("div");
    div.className = `flex items-center gap-5 p-4 rounded-xl transition-all ${status === 'active' ? 'bg-white border border-secondary-container shadow-sm ring-4 ring-secondary/5' : 'bg-surface border border-surface-container-high opacity-50'}`;
    div.innerHTML = `
        <div class="w-9 h-9 rounded-full flex items-center justify-center ${status === 'done' ? 'bg-secondary text-white' : 'bg-secondary-container text-secondary'}">
            <span class="material-symbols-outlined text-[18px] ${status === 'active' ? 'animate-pulse' : ''}">${status === 'done' ? 'check' : 'auto_awesome'}</span>
        </div>
        <div class="flex-1"><p class="font-body-md font-semibold text-primary text-sm">${text}</p></div>
        ${status === 'active' ? '<div class="flex gap-1 pr-2"><div class="w-1 h-1 bg-secondary rounded-full animate-bounce"></div><div class="w-1 h-1 bg-secondary rounded-full animate-bounce [animation-delay:-0.15s]"></div></div>' : ''}
    `;
    if (forgeSteps) forgeSteps.appendChild(div);
}

function jobPercent(job) {
  if (job.status === "completed") return 100;
  if (!job.total) return 10;
  return Math.floor((job.current / job.total) * 100);
}

function showSelection(clips) {
    showPhase("selection");
    const videoId = extractVideoId(lastRequest.youtube_url);
    if (momentsCountText) momentsCountText.textContent = `${clips.length} moments found`;
    clipList.innerHTML = clips.map(clip => `
        <div class="group relative bg-white rounded-2xl p-6 ambient-shadow hover:shadow-2xl transition-all duration-300 border border-outline-variant/20 hover:border-secondary/30 flex flex-col">
            <div class="relative w-full aspect-[9/16] bg-black rounded-xl overflow-hidden mb-6 shadow-inner border border-slate-100">
                <iframe class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300%] h-full pointer-events-none"
                    src="https://www.youtube.com/embed/${videoId}?start=${Math.floor(clip.start_sec)}&end=${Math.floor(clip.end_sec)}&autoplay=0&controls=0&mute=1&loop=1&playlist=${videoId}&modestbranding=1" 
                    frameborder="0" allow="autoplay; encrypted-media"></iframe>
            </div>
            <div class="absolute top-8 right-8 z-10"><input type="checkbox" value="${clip.rank}" checked class="clip-checkbox w-6 h-6 rounded-full border-outline-variant text-primary focus:ring-primary cursor-pointer transition-transform group-hover:scale-110 shadow-sm" /></div>
            <div class="mb-4 flex items-center justify-between"><span class="font-label-caps text-[10px] text-secondary bg-secondary-container/50 px-2.5 py-1 rounded-full uppercase tracking-wider">Moment 0${clip.rank}</span><div class="flex items-center gap-1.5"><span class="material-symbols-outlined text-error text-lg" style="font-variation-settings: 'FILL' 1;">trending_up</span><span class="font-bold text-lg text-primary">${clip.score}</span></div></div>
            <h3 class="font-h3 text-lg mb-2 group-hover:text-primary transition-colors line-clamp-1">${escapeHtml(clip.title)}</h3>
            <p class="font-body-md text-xs text-slate-500 mb-6 line-clamp-2 italic">"${escapeHtml(clip.hook)}"</p>
            <div class="mt-auto flex items-center justify-between"><span class="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">${Math.floor(clip.end_sec - clip.start_sec)} Sec</span><button onclick="renderSingle(${clip.rank})" class="text-[10px] font-black uppercase tracking-widest text-secondary hover:text-primary underline">Forge Moment</button></div>
        </div>
    `).join("");
}

async function renderSingle(rank) {
    showPhase("forge");
    updateForge(5, "Forging specific moment...");
    try {
        const job = await postJson("/render", { ...lastRequest, start_rank: rank, max_clips: 1, target_rank: rank });
        currentJobId = job.id;
        pollRenderJob(job.id);
    } catch (e) { alert(e.message); showPhase("selection"); }
}

function showFinalResults(files) {
    showPhase("result");
    renderOutput.innerHTML = files.map((file, i) => `
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start fade-in" style="animation-delay: ${i*0.2}s">
            <div class="lg:col-span-7 flex justify-center">
                <div class="relative group aspect-[9/16] w-full max-w-[400px] bg-black rounded-lg overflow-hidden shadow-2xl border-4 border-white">
                    <video controls src="/files?path=${encodeURIComponent(file)}" class="w-full h-full object-cover opacity-90"></video>
                </div>
            </div>
            <div class="lg:col-span-5 space-y-8">
                <div class="bg-white rounded-lg p-10 shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
                    <div class="space-y-6 text-left">
                        <div class="space-y-2">
                            <label class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest text-[10px] font-bold">Export Settings</label>
                            <div class="flex items-center justify-between p-4 bg-surface-container-low rounded-lg">
                                <div class="flex items-center gap-3"><span class="material-symbols-outlined text-secondary">hd</span><span class="font-body-md text-sm font-medium">Ultra High Definition</span></div>
                                <span class="font-body-md text-sm font-bold text-secondary">4K</span>
                            </div>
                        </div>
                        <div class="grid grid-cols-1 gap-4">
                            <a href="/files?path=${encodeURIComponent(file)}" download class="w-full py-5 bg-primary text-on-primary rounded-full font-h3 text-xl font-bold flex items-center justify-center gap-3 hover:opacity-90 transition-all active:scale-[0.98] shadow-xl">
                                <span class="material-symbols-outlined">download</span> Download HD
                            </a>
                            <button onclick="navigator.clipboard.writeText(window.location.origin + '/files?path=${encodeURIComponent(file)}')" class="w-full py-5 bg-secondary-container text-on-secondary-container border border-outline-variant/30 rounded-full font-h3 text-xl font-bold flex items-center justify-center gap-3 hover:bg-secondary-fixed transition-all active:scale-[0.98]">
                                <span class="material-symbols-outlined">content_copy</span> Copy Link
                            </button>
                        </div>
                    </div>
                </div>
                <div class="bg-secondary-container/30 border border-secondary-container rounded-lg p-6 flex gap-4 text-left">
                    <span class="material-symbols-outlined text-secondary">info</span>
                    <div><p class="font-body-md text-sm text-on-secondary-container font-bold">Auto-Archiving</p><p class="font-body-md text-[13px] text-on-secondary-container/80 mt-1">This link will expire in 7 days. Download your assets soon.</p></div>
                </div>
            </div>
        </div>
    `).join("<hr class='border-slate-100 my-32 opacity-0' />");
}

function escapeHtml(v) {
  return String(v || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
