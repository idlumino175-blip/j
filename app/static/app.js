// FINAL VERBATIM STABILITY BUILD
(function() {
    console.log("Clipper AI: Intelligence Suite Booting...");

    // 1. SELECT ALL ELEMENTS DEFENSIVELY
    const select = (id) => document.querySelector(id);
    const els = {
        analyzeForm: select("#analyzeForm"),
        youtubeUrlInput: select("#youtubeUrl"),
        landingPhase: select("#landingPhase"),
        forgePhase: select("#forgePhase"),
        selectionPhase: select("#selectionPhase"),
        resultPhase: select("#resultPhase"),
        myClipsPhase: select("#myClipsPhase"),
        apiPhase: select("#apiPhase"),
        navDashboard: select("#navDashboard"),
        navMyClips: select("#navMyClips"),
        navAPI: select("#navAPI"),
        historyGrid: select("#historyGrid"),
        apiGemini: select("#apiGemini"),
        saveApiBtn: select("#saveApiBtn"),
        apiMessage: select("#apiMessage"),
        urlPreview: select("#urlPreview"),
        previewTitle: select("#previewTitle"),
        previewThumb: select("#previewThumbImg"),
        previewChannel: select("#previewChannel"),
        clipList: select("#clipList"),
        renderOutput: select("#renderOutput"),
        forgeProgressCircle: select("#forgeProgressCircle"),
        forgePercentText: select("#forgePercentText"),
        forgeStatusLabel: select("#forgeStatusLabel"),
        forgeActionLabel: select("#forgeActionLabel"),
        forgeSteps: select("#forgeSteps"),
        momentsCountText: select("#momentsCountText"),
        authBtnNav: select("#authBtn"),
        signOutBtn: select("#signOutBtn"),
        userEmailDisplay: select("#userEmailDisplay"),
        authOverlay: select("#authOverlay"),
        closeAuth: select("#closeAuth"),
        signInBtn: select("#signInBtn"),
        signUpBtn: select("#signUpBtn"),
        authMessage: select("#authMessage"),
        authEmail: select("#authEmail"),
        authPassword: select("#authPassword"),
        generateSelectedBtn: select("#generateSelected"),
        cancelForgeBtn: select("#cancelForgeBtn"),
        maxClips: select("#maxClips"),
        speed: select("#speed")
    };

    // 2. GLOBAL STATE
    let lastRequest = null;
    let activeJobTimer = null;
    let currentJobId = null;
    let supabaseClient = null;
    let supabaseUser = null;
    let youtubeApiKey = null;
    let fluidProgressVal = 0;
    let fluidProgressInterval = null;

    // 3. IMMEDIATE UI ACTIONS (No dependencies)
    if (els.authBtnNav) {
        els.authBtnNav.addEventListener("click", () => {
            console.log("Clipper AI: Open Auth");
            els.authOverlay?.classList.remove("hidden");
        });
    }
    if (els.closeAuth) {
        els.closeAuth.addEventListener("click", () => els.authOverlay?.classList.add("hidden"));
    }

    // Phase Switching
    const showPhase = (name) => {
        const phases = [els.landingPhase, els.forgePhase, els.selectionPhase, els.resultPhase, els.myClipsPhase, els.apiPhase];
        phases.forEach(p => p?.classList.add("hidden"));
        
        [els.navDashboard, els.navMyClips, els.navAPI].forEach(link => {
            if (!link) return;
            link.classList.remove("text-primary", "font-semibold");
            link.classList.add("text-on-surface-variant", "font-medium");
            link.querySelector("span")?.classList.replace("w-full", "w-0");
        });

        if (name === "landing") {
            els.landingPhase?.classList.remove("hidden");
            els.navDashboard?.classList.add("text-primary", "font-semibold");
            els.navDashboard?.querySelector("span")?.classList.replace("w-0", "w-full");
            stopFluidProgress();
        } else if (name === "forge") {
            els.forgePhase?.classList.remove("hidden");
            startFluidProgress();
        } else if (name === "selection") {
            els.selectionPhase?.classList.remove("hidden");
            stopFluidProgress();
        } else if (name === "result") {
            els.resultPhase?.classList.remove("hidden");
            stopFluidProgress();
        } else if (name === "myclips") {
            els.myClipsPhase?.classList.remove("hidden");
            els.navMyClips?.classList.add("text-primary", "font-semibold");
            els.navMyClips?.querySelector("span")?.classList.replace("w-0", "w-full");
        } else if (name === "api") {
            els.apiPhase?.classList.remove("hidden");
            els.navAPI?.classList.add("text-primary", "font-semibold");
            els.navAPI?.querySelector("span")?.classList.replace("w-0", "w-full");
        }
        window.scrollTo(0, 0);
    };

    if (els.navDashboard) els.navDashboard.onclick = () => showPhase("landing");
    if (els.navMyClips) els.navMyClips.onclick = () => { showPhase("myclips"); fetchHistory(); };
    if (els.navAPI) els.navAPI.onclick = () => {
        showPhase("api");
        if (els.apiGemini) els.apiGemini.value = localStorage.getItem("gemini_key") || "";
    };

    if (els.saveApiBtn) {
        els.saveApiBtn.onclick = () => {
            localStorage.setItem("gemini_key", els.apiGemini.value.trim());
            els.apiMessage?.classList.remove("opacity-0");
            setTimeout(() => els.apiMessage?.classList.add("opacity-0"), 3000);
        };
    }

    // 4. PREVIEW LOGIC
    const extractVideoId = (url) => {
        const regExp = /^.*(youtu\.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
        const match = String(url || "").match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    };

    if (els.youtubeUrlInput) {
        els.youtubeUrlInput.oninput = async (e) => {
            const videoId = extractVideoId(e.target.value.trim());
            if (videoId) {
                els.urlPreview?.classList.remove("hidden");
                if (!youtubeApiKey) { if (els.previewTitle) els.previewTitle.textContent = "Syncing with server..."; return; }
                if (els.previewTitle) els.previewTitle.textContent = "Fetching intelligence...";
                try {
                    const resp = await fetch(`https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${videoId}&key=${youtubeApiKey}`);
                    const data = await resp.json();
                    if (data.items && data.items.length > 0) {
                        const snip = data.items[0].snippet;
                        if (els.previewTitle) els.previewTitle.textContent = snip.title;
                        if (els.previewThumb) els.previewThumb.src = snip.thumbnails.medium.url;
                        if (els.previewChannel) els.previewChannel.textContent = snip.channelTitle;
                    }
                } catch (err) { console.error("Preview failed", err); }
            } else {
                els.urlPreview?.classList.add("hidden");
            }
        };
    }

    // 5. CORE SYSTEM INIT
    document.addEventListener("DOMContentLoaded", () => {
        fetch("/app-config?t=" + new Date().getTime())
            .then(r => r.json())
            .then(config => {
                youtubeApiKey = config.youtube_api_key;
                if (!config.auth_enabled) return;
                
                supabaseClient = supabase.createClient(config.supabase_url, config.supabase_anon_key);
                
                supabaseClient.auth.onAuthStateChange((event, session) => {
                    const user = session?.user || null;
                    supabaseUser = user;
                    if (user) {
                        els.authOverlay?.classList.add("hidden");
                        els.authBtnNav?.classList.add("hidden");
                        if (els.userEmailDisplay) { els.userEmailDisplay.textContent = user.email; els.userEmailDisplay.classList.remove("hidden"); }
                        els.signOutBtn?.classList.remove("hidden");
                    } else {
                        els.userEmailDisplay?.classList.add("hidden");
                        els.signOutBtn?.classList.add("hidden");
                        els.authBtnNav?.classList.remove("hidden");
                    }
                });
                
                // Check initial session
                supabaseClient.auth.getSession().then(({ data: { session } }) => {
                    if (session?.user) {
                        supabaseUser = session.user;
                        if (els.userEmailDisplay) { els.userEmailDisplay.textContent = session.user.email; els.userEmailDisplay.classList.remove("hidden"); }
                    }
                });
            })
            .catch(err => console.error("System init failed", err));
    });

    // 6. ACTION HANDLERS
    const postJson = async (url, payload) => {
        const headers = { "Content-Type": "application/json" };
        if (supabaseUser) {
            const { data: { session } } = await supabaseClient.auth.getSession();
            if (session?.access_token) {
                headers.Authorization = `Bearer ${session.access_token}`;
            }
        }
        const resp = await fetch(url, { method: "POST", headers, body: JSON.stringify(payload) });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Request failed");
        return data;
    };

    if (els.analyzeForm) {
        els.analyzeForm.onsubmit = async (e) => {
            e.preventDefault();
            const payload = {
                youtube_url: els.youtubeUrlInput.value,
                max_clips: Number(els.maxClips?.value || 10),
                min_duration_sec: 20,
                max_duration_sec: 75,
                speed: Number(els.speed?.value || 1.1),
                style: "black-box",
                gemini_api_key: localStorage.getItem("gemini_key") || null,
            };
            lastRequest = payload;
            showPhase("forge");
            try {
                const job = await postJson("/render", payload);
                currentJobId = job.id;
                pollJob(job.id);
            } catch (err) { alert(err.message); showPhase("landing"); }
        };
    }

    if (els.cancelForgeBtn) {
        els.cancelForgeBtn.onclick = async () => {
            if (!currentJobId) return;
            if (confirm("Cancel intelligence extraction?")) {
                try {
                    await postJson(`/render/jobs/${currentJobId}/cancel`, {});
                    if (activeJobTimer) clearInterval(activeJobTimer);
                    showPhase("landing");
                } catch (e) { showPhase("landing"); }
            }
        };
    }

    // 7. RENDERING & UTILS
    const pollJob = (jobId) => {
        if (activeJobTimer) clearInterval(activeJobTimer);
        activeJobTimer = setInterval(async () => {
            const job = await fetch(`/render/jobs/${jobId}`).then(r => r.json());
            if (job.status === "cancelled") { clearInterval(activeJobTimer); showPhase("landing"); return; }
            
            if (job.logs && job.logs.length > 0) {
                const logBox = select("#forgeLogs");
                if (logBox) {
                    logBox.innerHTML = job.logs.map(l => `<div class="flex gap-3"><span class="text-slate-500 font-bold">[${l.time}]</span><span class="text-secondary">${l.msg}</span></div>`).join("");
                    logBox.scrollTop = logBox.scrollHeight;
                }
            }

            if (job.status === "completed") {
                clearInterval(activeJobTimer);
                if (job.phase === "Completed") showFinalResults(job.files);
                else showSelection(job.clips);
            } else if (job.status === "failed") {
                clearInterval(activeJobTimer);
                alert(job.error);
                showPhase("landing");
            }
        }, 2000);
    };

    const startFluidProgress = () => {
        fluidProgressVal = 5;
        if (fluidProgressInterval) clearInterval(fluidProgressInterval);
        fluidProgressInterval = setInterval(() => {
            if (fluidProgressVal < 98) {
                fluidProgressVal += (Math.random() * 0.3);
                updateRing(Math.floor(fluidProgressVal));
            }
        }, 500);
    };

    const stopFluidProgress = () => { if (fluidProgressInterval) clearInterval(fluidProgressInterval); fluidProgressInterval = null; };

    const updateRing = (percent) => {
        if (els.forgeProgressCircle) els.forgeProgressCircle.style.strokeDashoffset = 754 - (754 * percent / 100);
        if (els.forgePercentText) els.forgePercentText.textContent = `${percent}%`;
    };

    const showSelection = (clips) => {
        showPhase("selection");
        const videoId = extractVideoId(lastRequest.youtube_url);
        if (els.momentsCountText) els.momentsCountText.textContent = `${clips.length} moments found`;
        els.clipList.innerHTML = clips.map(clip => `
            <div class="clip-card">
                <div class="clip-video">
                    <iframe src="https://www.youtube.com/embed/${videoId}?start=${Math.floor(clip.start_sec)}&end=${Math.floor(clip.end_sec)}&autoplay=0&controls=0&mute=1&loop=1&playlist=${videoId}&modestbranding=1" 
                        frameborder="0" allow="autoplay; encrypted-media"></iframe>
                </div>
                <div class="clip-body">
                    <div class="clip-rank">Clip ${String(clip.rank).padStart(2,'0')}</div>
                    <div class="clip-title">${clip.title}</div>
                    <div class="clip-score">${clip.score}<span>/ 100</span></div>
                    <button onclick="renderSingle(${clip.rank})" class="forge-btn">⚡ Forge This Clip</button>
                </div>
            </div>
        `).join("");
    };

    const showFinalResults = (files) => {
        showPhase("result");
        els.renderOutput.innerHTML = files.map((file, i) => `
            <div class="result-item">
                <div style="display:flex;justify-content:center;">
                    <div class="result-player">
                        <video controls src="/files?path=${encodeURIComponent(file)}"></video>
                    </div>
                </div>
                <div class="result-panel">
                    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--accent);">Asset ${String(i+1).padStart(2,'0')}</div>
                    <h2 style="font-family:'Instrument Serif',serif;font-size:36px;font-weight:400;line-height:1.2;">Your clip<br/>is ready.</h2>
                    <p style="color:var(--text-2);font-size:15px;line-height:1.7;">Optimized for TikTok, Instagram Reels & YouTube Shorts. Download and post.</p>
                    <a href="/files?path=${encodeURIComponent(file)}" download class="download-btn">
                        <span class="material-symbols-outlined" style="font-size:20px;">download</span>
                        Download HD
                    </a>
                </div>
            </div>
        `).join("");
    };

    async function fetchHistory() {
        if (!els.historyGrid) return;
        els.historyGrid.innerHTML = `<p class="col-span-full text-center py-20 opacity-50">Syncing history...</p>`;
        try {
            const resp = await fetch("/renders");
            const clips = await resp.json();
            els.historyGrid.innerHTML = clips.map(c => `<div class="history-card"><div class="history-video"><video src="/files?path=${encodeURIComponent(c.path)}"></video></div><div class="history-card-body"><div class="history-name">${c.name}</div><a href="/files?path=${encodeURIComponent(c.path)}" download class="history-dl">Download</a></div></div>`).join("");
        } catch (e) { els.historyGrid.innerHTML = "Error."; }
    }

    // 8. ATTACH LOGIN EVENTS
    if (els.signInBtn) {
        els.signInBtn.onclick = async () => {
            const email = els.authEmail?.value;
            const pass = els.authPassword?.value;
            if (els.authMessage) els.authMessage.textContent = "VERIFYING...";
            try { 
                const { error } = await supabaseClient.auth.signInWithPassword({ email, password: pass });
                if (error) throw error;
            }
            catch (e) { if (els.authMessage) els.authMessage.textContent = e.message; }
        };
    }
    if (els.signUpBtn) {
        els.signUpBtn.onclick = async () => {
            const email = els.authEmail?.value;
            const pass = els.authPassword?.value;
            if (els.authMessage) els.authMessage.textContent = "CREATING...";
            try { 
                const { error } = await supabaseClient.auth.signUp({ email, password: pass });
                if (error) throw error;
                if (els.authMessage) els.authMessage.textContent = "Check your email for confirmation.";
            }
            catch (e) { if (els.authMessage) els.authMessage.textContent = e.message; }
        };
    }
    if (els.signOutBtn) els.signOutBtn.onclick = () => supabaseClient.auth.signOut();

    // 9. WINDOW ERROR CATCHER (FOR VERCEL)
    window.onerror = function(msg, url, line) {
        alert("CRITICAL ERROR: " + msg + "\nLine: " + line);
    };

    console.log("Clipper AI: Suite Ready.");
})();
