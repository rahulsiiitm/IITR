const appWindow = document.getElementById("appWindow");
const bubbleBtn = document.getElementById("bubbleBtn");
const closeBtn = document.getElementById("closeBtn");
const chatArea = document.getElementById("chatArea");
const inputForm = document.getElementById("inputForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const welcomeMessage = document.getElementById("welcomeMessage");
const voiceToggleBtn = document.getElementById("voiceToggleBtn");
const voiceToggleIcon = document.getElementById("voiceToggleIcon");
const voiceModeBtn = document.getElementById("voiceModeBtn");
const voiceModeOverlay = document.getElementById("voiceModeOverlay");
const exitVoiceModeBtn = document.getElementById("exitVoiceModeBtn");
const voiceStatusText = document.getElementById("voiceStatusText");
const voiceUserSpeech = document.getElementById("voiceUserSpeech");
const voiceBotSpeech = document.getElementById("voiceBotSpeech");

let isProcessing = false;
let currentSessionId = null;
let msgCount = 0;
let autoReadAloud = localStorage.getItem("autoReadAloud") === "true";
let voiceModeState = "inactive"; // "listening" | "thinking" | "speaking" | "inactive"
let recognitionReceivedResult = false;
let audioUnlocked = false; // tracks whether browser autoplay has been unlocked

// Silent WAV (smallest valid file) used to unlock browser autoplay on first user click
const SILENT_WAV = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  // Play a silent clip synchronously during the user-gesture event so Chrome
  // grants this tab permission to call audio.play() from async code later
  const silent = new Audio(SILENT_WAV);
  silent.play().catch(() => { });
}

// ── Toggle ────────────────────────────────────────────
bubbleBtn.addEventListener("click", () => {
  appWindow.classList.remove("hidden");
  bubbleBtn.classList.add("hidden");
  messageInput.focus();
});

closeBtn.addEventListener("click", () => {
  appWindow.classList.add("hidden");
  bubbleBtn.classList.remove("hidden");
});

// ── Submit ────────────────────────────────────────────
inputForm.addEventListener("submit", (e) => {
  e.preventDefault();
  unlockAudio(); // unlock audio context on enter key / send click
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;
  handleMessage(text);
});

// ── Clear ─────────────────────────────────────────────
clearBtn.addEventListener("click", () => {
  stopSpeaking();
  chatArea
    .querySelectorAll(".msg-wrapper, .msg-divider")
    .forEach((el) => el.remove());
  welcomeMessage.style.display = "flex";
  currentSessionId = null;
  msgCount = 0;
});

// ── Suggestions ───────────────────────────────────────
document.addEventListener("click", (e) => {
  const card = e.target.closest(".suggestion-card");
  if (card && !isProcessing) {
    const question = card.getAttribute("data-question");
    if (question) handleMessage(question);
  }
});

// ── Core handler ──────────────────────────────────────
function handleMessage(text) {
  stopSpeaking();
  welcomeMessage.style.display = "none";
  msgCount++;

  if (msgCount > 1) addDivider();

  addMsg(text, "user");
  messageInput.value = "";

  isProcessing = true;
  sendBtn.disabled = true;
  const loader = addLoader();

  streamFromBackend(text, loader);
}

// ── Add message ───────────────────────────────────────
function addMsg(text, type, sources, debug) {
  const wrapper = document.createElement("div");
  wrapper.className = `msg-wrapper ${type}`;

  // Meta row (avatar + author label)
  const meta = document.createElement("div");
  meta.className = "msg-meta";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.setAttribute("aria-hidden", "true");

  if (type === "user") {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  } else {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;
  }

  const author = document.createElement("span");
  author.className = "msg-author";
  author.textContent = type === "user" ? "You" : "Sutra";

  const time = document.createElement("span");
  time.className = "msg-time";
  time.textContent = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  meta.appendChild(avatar);
  meta.appendChild(author);
  meta.appendChild(time);

  // Bubble
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  if (type === "user") {
    bubble.textContent = text;
  } else {
    if (typeof marked !== "undefined") {
      marked.setOptions({ breaks: true, gfm: true });
      bubble.innerHTML = marked.parse(text);
    } else {
      bubble.textContent = text;
    }
  }

  // Sources
  if (type === "bot" && sources && sources.length) {
    const sourceContainer = document.createElement("div");
    sourceContainer.className = "source-container";

    const grouped = {};
    sources.forEach((s) => {
      const doc = s.document || "Document";
      const filename = s.filename || null;
      if (!grouped[doc]) grouped[doc] = { filename, pages: [] };
      grouped[doc].pages.push(s.page);
    });

    for (const [docName, info] of Object.entries(grouped)) {
      const pill = document.createElement("span");
      pill.className = "source-pill";
      if (info.filename) {
        pill.classList.add("clickable");
        pill.title = "View PDF Document";
        pill.addEventListener("click", () => {
          openPdfViewer(info.filename, info.pages[0] || 1);
        });
      }
      const unique = [...new Set(info.pages)].sort((a, b) => a - b);
      const label = unique.length === 1 ? "p." : "pp.";
      pill.textContent = `${docName} — ${label} ${unique.join(", ")}`;
      sourceContainer.appendChild(pill);
    }

    bubble.appendChild(sourceContainer);
  }

  // Debug panel (hidden by CSS in prod, kept for dev)
  if (type === "bot" && debug && debug.length) {
    const toggle = document.createElement("button");
    toggle.className = "debug-toggle";
    toggle.textContent = "Show retrieved chunks";

    const panel = document.createElement("div");
    panel.className = "debug-panel";
    panel.style.display = "none";

    debug.forEach((item, i) => {
      const entry = document.createElement("div");
      entry.className = "debug-entry";
      entry.innerHTML = `<strong>Chunk ${i + 1}</strong> — Score: ${item.rerank_score.toFixed(3)}, Page ${item.page}<br><small>${escapeHtml(item.chunk)}</small>`;
      panel.appendChild(entry);
    });

    toggle.addEventListener("click", () => {
      const isOpen = panel.style.display !== "none";
      panel.style.display = isOpen ? "none" : "block";
      toggle.textContent = isOpen
        ? "Show retrieved chunks"
        : "Hide retrieved chunks";
    });

    bubble.appendChild(toggle);
    bubble.appendChild(panel);
  }

  if (type === "bot") {
    setupBotSpeakControl(wrapper, text);
  }

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
}

// ── Loader ────────────────────────────────────────────
function addLoader() {
  const wrapper = document.createElement("div");
  wrapper.className = "msg-wrapper bot";

  const meta = document.createElement("div");
  meta.className = "msg-meta";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;

  const author = document.createElement("span");
  author.className = "msg-author";
  author.textContent = "Sutra";

  meta.appendChild(avatar);
  meta.appendChild(author);

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML =
    '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
  return wrapper;
}

// ── Divider ───────────────────────────────────────────
function addDivider() {
  const div = document.createElement("div");
  div.className = "msg-divider";
  div.innerHTML = "<span>· · ·</span>";
  chatArea.appendChild(div);
}

// ── Escape HTML ───────────────────────────────────────
function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── API (streaming) ───────────────────────────────────
const API_BASE = window.API_SAME_ORIGIN
  ? window.location.origin
  : `http://${window.location.hostname}:${window.API_PORT || 52000}`;

async function streamFromBackend(question, loaderEl) {
  const headers = { "Content-Type": "application/json" };
  if (window.API_KEY) headers["X-API-Key"] = window.API_KEY;

  const payload = { question };
  if (currentSessionId) payload.session_id = currentSessionId;

  let res;
  try {
    res = await fetch(`${API_BASE}/ask/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    loaderEl.remove();
    addMsg(
      `Cannot reach the API at ${API_BASE}. Make sure the server is running.`,
      "bot",
    );
    isProcessing = false;
    sendBtn.disabled = false;
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    loaderEl.remove();
    addMsg(err.detail || "Backend request failed.", "bot");
    isProcessing = false;
    sendBtn.disabled = false;
    return;
  }

  // Keep the loader visible while the pipeline runs on the backend.
  // The bot bubble is created lazily on the first token, then the loader is removed.
  let botBubble = null;
  let accumulated = "";
  let sourcesData = [];

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function _ensureBubble() {
    if (botBubble) return;
    loaderEl.remove();
    const { bubble } = addStreamingMsg();
    botBubble = bubble;
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let event;
        try {
          event = JSON.parse(line.slice(6));
        } catch {
          continue;
        }

        if (event.type === "token") {
          _ensureBubble();
          accumulated += event.content;
          // Live-render markdown as tokens arrive
          if (typeof marked !== "undefined") {
            marked.setOptions({ breaks: true, gfm: true });
            botBubble.innerHTML = marked.parse(accumulated);
          } else {
            botBubble.textContent = accumulated;
          }
          if (voiceModeState === "thinking" || voiceModeState === "speaking") {
            voiceBotSpeech.textContent = accumulated;
          }
          chatArea.scrollTop = chatArea.scrollHeight;
        } else if (event.type === "done") {
          _ensureBubble(); // handles instant shortcuts that skip token events
          if (event.session_id) currentSessionId = event.session_id;
          sourcesData = event.sources || [];
          // Final markdown render
          if (typeof marked !== "undefined") {
            marked.setOptions({ breaks: true, gfm: true });
            botBubble.innerHTML = marked.parse(accumulated);
          }
          // Append sources
          if (sourcesData.length) {
            const sourceContainer = document.createElement("div");
            sourceContainer.className = "source-container";
            const grouped = {};
            sourcesData.forEach((s) => {
              const doc = s.document || "Document";
              const filename = s.filename || null;
              if (!grouped[doc]) grouped[doc] = { filename, pages: [] };
              grouped[doc].pages.push(s.page);
            });
            for (const [docName, info] of Object.entries(grouped)) {
              const pill = document.createElement("span");
              pill.className = "source-pill";
              if (info.filename) {
                pill.classList.add("clickable");
                pill.title = "View PDF Document";
                pill.addEventListener("click", () => {
                  openPdfViewer(info.filename, info.pages[0] || 1);
                });
              }
              const unique = [...new Set(info.pages)].sort((a, b) => a - b);
              const label = unique.length === 1 ? "p." : "pp.";
              pill.textContent = `${docName} — ${label} ${unique.join(", ")}`;
              sourceContainer.appendChild(pill);
            }
            botBubble.appendChild(sourceContainer);
          }

          const wrapper = botBubble.closest(".msg-wrapper");
          setupBotSpeakControl(wrapper, accumulated);
          if (voiceModeState === "thinking" || voiceModeState === "speaking") {
            voiceModeState = "speaking";
            voiceModeOverlay.classList.remove("listening", "thinking");
            voiceModeOverlay.classList.add("speaking");
            voiceStatusText.textContent = "Speaking...";
            void speakVoiceModeMessage(accumulated);
          } else if (autoReadAloud) {
            speakMessage(wrapper);
          }

          chatArea.scrollTop = chatArea.scrollHeight;
        } else if (event.type === "error") {
          _ensureBubble();
          botBubble.textContent = event.content || "An error occurred.";
        }
      }
    }
  } catch (err) {
    console.error("Stream read error:", err);
    _ensureBubble();
    if (!accumulated)
      botBubble.textContent = "Connection interrupted. Please try again.";
  } finally {
    isProcessing = false;
    sendBtn.disabled = false;
  }
}

// ── Streaming bubble ──────────────────────────────────
function addStreamingMsg() {
  const wrapper = document.createElement("div");
  wrapper.className = "msg-wrapper bot";

  const meta = document.createElement("div");
  meta.className = "msg-meta";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;

  const author = document.createElement("span");
  author.className = "msg-author";
  author.textContent = "Sutra";

  const time = document.createElement("span");
  time.className = "msg-time";
  time.textContent = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  meta.appendChild(avatar);
  meta.appendChild(author);
  meta.appendChild(time);

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
  return { wrapper, bubble };
}

// ── Legacy non-streaming API (kept for fallback) ───────
async function sendToBackend(question) {
  const headers = { "Content-Type": "application/json" };
  if (window.API_KEY) headers["X-API-Key"] = window.API_KEY;

  const payload = { question };
  if (currentSessionId) payload.session_id = currentSessionId;

  let res;
  try {
    res = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      `Cannot reach the API at ${API_BASE}. Run ./scripts/run_server.sh and open the URL it prints.`,
    );
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : JSON.stringify(detail) || res.statusText;
    throw new Error(msg || "Backend request failed");
  }

  const data = await res.json();
  if (data.session_id) currentSessionId = data.session_id;
  return data;
}

// ── Voice Toggle Button ────────────────────────────────
function updateVoiceToggleUI() {
  if (!voiceToggleBtn) return;
  if (autoReadAloud) {
    voiceToggleBtn.classList.add("active");
    voiceToggleBtn.title = "Auto Read Aloud (On)";
    if (voiceToggleIcon) voiceToggleIcon.innerHTML = `
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
    `;
  } else {
    voiceToggleBtn.classList.remove("active");
    voiceToggleBtn.title = "Auto Read Aloud (Off)";
    if (voiceToggleIcon) voiceToggleIcon.innerHTML = `
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    `;
  }
}

updateVoiceToggleUI();

if (voiceToggleBtn) {
  voiceToggleBtn.addEventListener("click", () => {
    autoReadAloud = !autoReadAloud;
    localStorage.setItem("autoReadAloud", autoReadAloud);
    updateVoiceToggleUI();
    if (!autoReadAloud) {
      stopSpeaking();
    }
  });
}

// ── Speech Synthesis (Voice Output) ───────────────────
let activeSpeakerWrapper = null;

function setupBotSpeakControl(wrapper, text) {
  wrapper.dataset.rawText = text;

  const meta = wrapper.querySelector(".msg-meta");
  if (!meta || meta.querySelector(".speak-btn")) return;

  const speakBtn = document.createElement("button");
  speakBtn.className = "speak-btn";
  speakBtn.title = "Read aloud";
  speakBtn.setAttribute("aria-label", "Read aloud");
  speakBtn.innerHTML = `
    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  `;

  const soundwave = document.createElement("div");
  soundwave.className = "soundwave hidden";
  soundwave.innerHTML = `
    <div class="soundwave-bar"></div>
    <div class="soundwave-bar"></div>
    <div class="soundwave-bar"></div>
    <div class="soundwave-bar"></div>
  `;

  meta.appendChild(speakBtn);
  meta.appendChild(soundwave);

  speakBtn.addEventListener("click", () => {
    unlockAudio();
    speakMessage(wrapper);
  });
}

function stopSpeaking() {
  // Stop active HTML5 Audio — null the ref first so callbacks don't fire
  if (activeAudio) {
    const el = activeAudio;
    activeAudio = null;
    el.onended = null;
    el.onerror = null;
    Promise.resolve().then(() => { try { el.pause(); el.src = ""; } catch (_) { } });
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (activeSpeakerWrapper) {
    const speakBtn = activeSpeakerWrapper.querySelector(".speak-btn");
    const soundwave = activeSpeakerWrapper.querySelector(".soundwave");
    if (speakBtn) {
      speakBtn.classList.remove("playing");
      speakBtn.title = "Read aloud";
      speakBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        </svg>
      `;
    }
    if (soundwave) {
      soundwave.classList.add("hidden");
    }
    activeSpeakerWrapper = null;
  }
}

function speakMessage(wrapper) {
  if (activeSpeakerWrapper === wrapper) {
    stopSpeaking();
    return;
  }

  stopSpeaking();

  const textToRead = wrapper.dataset.rawText;
  if (!textToRead) return;

  const cleanText = stripMarkdown(textToRead);
  if (!cleanText) return;

  activeSpeakerWrapper = wrapper;
  const speakBtn = wrapper.querySelector(".speak-btn");
  const soundwave = wrapper.querySelector(".soundwave");

  if (speakBtn) {
    speakBtn.classList.add("playing");
    speakBtn.title = "Stop reading";
    speakBtn.innerHTML = `
      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="4" width="16" height="16" rx="2" />
      </svg>
    `;
  }
  if (soundwave) {
    soundwave.classList.remove("hidden");
  }

  // Increment generation to invalidate any currently pending TTS fetches
  speakGeneration++;
  const myGeneration = speakGeneration;

  try {
    const fetchHeaders = { "Content-Type": "application/json" };
    if (window.API_KEY) fetchHeaders["X-API-Key"] = window.API_KEY;

    fetch("/voice/synthesize", {
      method: "POST",
      headers: fetchHeaders,
      body: JSON.stringify({ text: cleanText })
    })
      .then(res => {
        if (!res.ok) throw new Error("TTS synthesis failed");
        return res.blob();
      })
      .then(audioBlob => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(audioBlob);
      }))
      .then(dataUrl => {
        // Abort if another speak request started while we were awaiting
        if (myGeneration !== speakGeneration) return;

        activeAudio = new Audio(dataUrl);

        activeAudio.onended = () => {
          activeAudio = null;
          if (activeSpeakerWrapper === wrapper && myGeneration === speakGeneration) {
            stopSpeaking();
          }
        };

        activeAudio.onerror = () => {
          activeAudio = null;
          if (activeSpeakerWrapper === wrapper && myGeneration === speakGeneration) {
            stopSpeaking();
          }
        };

        activeAudio.play().catch(err => {
          console.warn("Read-aloud play failed, falling back:", err.message);
          activeAudio = null;
          if (myGeneration === speakGeneration) {
            fallbackToBrowserSpeechOnWrapper(wrapper, cleanText);
          }
        });
      })
      .catch(err => {
        console.warn("TTS fetch failed, falling back:", err.message);
        if (myGeneration === speakGeneration) {
          fallbackToBrowserSpeechOnWrapper(wrapper, cleanText);
        }
      });
  } catch (err) {
    console.warn("TTS error, falling back:", err.message);
    if (myGeneration === speakGeneration) {
      fallbackToBrowserSpeechOnWrapper(wrapper, cleanText);
    }
  }
}

function fallbackToBrowserSpeechOnWrapper(wrapper, cleanText) {
  if (!window.speechSynthesis) {
    stopSpeaking();
    return;
  }

  const utterance = new SpeechSynthesisUtterance(cleanText);
  const voices = window.speechSynthesis.getVoices();
  const preferredVoice = voices.find(v =>
    v.lang.startsWith("en-") &&
    (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Microsoft"))
  ) || voices.find(v => v.lang.startsWith("en"));

  if (preferredVoice) {
    utterance.voice = preferredVoice;
  }

  utterance.onend = () => {
    if (activeSpeakerWrapper === wrapper) {
      stopSpeaking();
    }
  };

  utterance.onerror = (e) => {
    console.error("Speech synthesis error:", e);
    if (activeSpeakerWrapper === wrapper) {
      stopSpeaking();
    }
  };

  window.speechSynthesis.speak(utterance);
}

function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[\*_]{1,3}([^*_]+)[\*_]{1,3}/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^#+\s+(.+)$/gm, "$1")
    .replace(/^\s*[\*\-\+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Pre-load voices if supported
if (window.speechSynthesis && window.speechSynthesis.onvoiceschanged !== undefined) {
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}

// ── Voice Mode (Continuous ChatGPT-Style Call Mode with Whisper & gTTS) ────
let activeAudio = null;
let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioContext = null;
let vadAnimationFrame = null;
let speakGeneration = 0;  // incremented each time we start speaking; guards stale onended callbacks

// Silent WAV (smallest valid file) used to unlock browser autoplay on first user click
// VAD tuning — raise threshold if room noise triggers false silence detections
const SILENCE_THRESHOLD = 22;    // avg FFT amplitude below which we count as silence
const SILENCE_START_DELAY = 2000;  // ms after recording starts before silence countdown begins
const SILENCE_DURATION = 2000;  // ms of continuous silence that triggers submission
const MAX_RECORDING_MS = 30000; // hard cap — stop even if VAD never fires

async function startRecording() {
  audioChunks = [];
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    console.error("Microphone access denied:", err);
    alert("Microphone permission denied. Exiting Voice Mode.");
    exitVoiceMode();
    return;
  }

  mediaRecorder = new MediaRecorder(mediaStream);

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };

  // Build blob FIRST, then stop tracks so last chunk is never lost
  mediaRecorder.onstop = async () => {
    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
    // Release mic tracks
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
    mediaStream = null;

    // Guard: don't process anything if voice mode was already closed
    if (voiceModeState === "inactive") return;

    if (audioBlob.size > 2000) {
      await sendAudioToWhisper(audioBlob);
    } else if (voiceModeState === "listening") {
      startRecording(); // too short / silence — try again
    }
  };

  // Web Audio VAD
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContextClass();
    const source = audioContext.createMediaStreamSource(mediaStream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    mediaRecorder.start();
    if (voiceModeState === "listening") {
      voiceModeOverlay.classList.remove("thinking", "speaking");
      voiceModeOverlay.classList.add("listening");
      voiceStatusText.textContent = "Listening...";
    }

    const startTime = Date.now();
    // lastSoundTime starts AFTER the startup grace so mic warm-up noise
    // doesn't immediately reset the silence countdown
    let lastSoundTime = startTime + SILENCE_START_DELAY;

    // Hard-cap timer — always stop recording after MAX_RECORDING_MS
    const hardCapTimer = setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
    }, MAX_RECORDING_MS);

    function checkVolume() {
      if (voiceModeState !== "listening") {
        clearTimeout(hardCapTimer);
        if (audioContext && audioContext.state !== "closed") audioContext.close();
        return;
      }

      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
      const average = sum / bufferLength;
      const now = Date.now();

      // Only start tracking silence after the startup grace period
      if (now > startTime + SILENCE_START_DELAY && average > SILENCE_THRESHOLD) {
        lastSoundTime = now;
      }

      const silenceElapsed = now - lastSoundTime;
      if (now > startTime + SILENCE_START_DELAY && silenceElapsed > SILENCE_DURATION) {
        clearTimeout(hardCapTimer);
        if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
        if (audioContext && audioContext.state !== "closed") audioContext.close();
      } else {
        vadAnimationFrame = requestAnimationFrame(checkVolume);
      }
    }

    vadAnimationFrame = requestAnimationFrame(checkVolume);
  } catch (err) {
    console.error("VAD initialization failed:", err);
  }
}

async function sendAudioToWhisper(blob) {
  // Don't process if voice mode was closed while we were recording
  if (voiceModeState === "inactive") return;

  voiceModeState = "thinking";
  voiceModeOverlay.classList.remove("listening", "speaking");
  voiceModeOverlay.classList.add("thinking");
  voiceStatusText.textContent = "Thinking...";

  const formData = new FormData();
  formData.append("file", blob, "voice.webm");

  try {
    const fetchHeaders = {};
    if (window.API_KEY) fetchHeaders["X-API-Key"] = window.API_KEY;

    const res = await fetch("/voice/transcribe", {
      method: "POST",
      headers: fetchHeaders,
      body: formData
    });
    if (!res.ok) throw new Error("Whisper transcription failed");
    const data = await res.json();
    const transcript = data.text.trim();

    if (transcript) {
      voiceUserSpeech.textContent = `“${transcript}”`;
      voiceBotSpeech.textContent = "";
      handleMessage(transcript);
    } else {
      startVoiceModeListening();
    }
  } catch (err) {
    console.error("Transcription error:", err);
    voiceBotSpeech.textContent = "Sorry, I couldn't hear you clearly. Please try again.";
    setTimeout(startVoiceModeListening, 2000);
  }
}

async function speakVoiceModeMessage(text) {
  // Stop any currently-playing audio without touching speakGeneration
  if (activeAudio) {
    const el = activeAudio;
    activeAudio = null;
    el.onended = null;
    el.onerror = null;
    Promise.resolve().then(() => { try { el.pause(); el.src = ""; } catch (_) { } });
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();

  const cleanText = stripMarkdown(text);
  if (!cleanText) {
    startVoiceModeListening();
    return;
  }

  // Bump generation NOW (before the async fetch) so any previous stale
  // onended callbacks that fire during the await know they are outdated
  speakGeneration++;
  const myGeneration = speakGeneration;

  try {
    const fetchHeaders = { "Content-Type": "application/json" };
    if (window.API_KEY) fetchHeaders["X-API-Key"] = window.API_KEY;

    const res = await fetch("/voice/synthesize", {
      method: "POST",
      headers: fetchHeaders,
      body: JSON.stringify({ text: cleanText }),
    });

    if (!res.ok) throw new Error(`TTS failed: ${res.status}`);

    const audioBlob = await res.blob();

    // If user exited voice mode or a newer speak call started while we awaited
    if (myGeneration !== speakGeneration || voiceModeState !== "speaking") {
      return;
    }

    // Use base64 data URL instead of blob URL — blob URLs can be
    // garbage-collected before play() resolves, causing AbortError
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(audioBlob);
    });

    // Check again after the async FileReader
    if (myGeneration !== speakGeneration || voiceModeState !== "speaking") {
      return;
    }

    activeAudio = new Audio(dataUrl);

    activeAudio.onended = () => {
      activeAudio = null;
      if (voiceModeState === "speaking" && myGeneration === speakGeneration) {
        startVoiceModeListening();
      }
    };

    activeAudio.onerror = (e) => {
      console.error("Audio error:", e);
      activeAudio = null;
      if (voiceModeState === "speaking" && myGeneration === speakGeneration) {
        fallbackToBrowserSpeech(cleanText, myGeneration);
      }
    };

    activeAudio.play().catch(err => {
      console.warn("Audio play failed, falling back:", err.message);
      activeAudio = null;
      if (voiceModeState === "speaking" && myGeneration === speakGeneration) {
        fallbackToBrowserSpeech(cleanText, myGeneration);
      }
    });

  } catch (err) {
    console.error("TTS fetch error:", err);
    if (myGeneration === speakGeneration && voiceModeState === "speaking") {
      fallbackToBrowserSpeech(cleanText, myGeneration);
    }
  }
}

function fallbackToBrowserSpeech(cleanText, generation) {
  if (!window.speechSynthesis) {
    startVoiceModeListening();
    return;
  }

  const utterance = new SpeechSynthesisUtterance(cleanText);
  const voices = window.speechSynthesis.getVoices();
  // Prefer an Indian English voice if available
  const preferredVoice =
    voices.find(v => v.lang === "en-IN") ||
    voices.find(v => v.lang.startsWith("en-") &&
      (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Microsoft"))) ||
    voices.find(v => v.lang.startsWith("en"));

  if (preferredVoice) utterance.voice = preferredVoice;

  utterance.onend = () => {
    if (voiceModeState === "speaking" && generation === speakGeneration) {
      startVoiceModeListening();
    }
  };
  utterance.onerror = (e) => {
    console.error("Fallback speech error:", e);
    if (voiceModeState === "speaking" && generation === speakGeneration) {
      startVoiceModeListening();
    }
  };

  window.speechSynthesis.speak(utterance);
}

function exitVoiceMode() {
  voiceModeState = "inactive";
  stopSpeaking();

  // Kill the onstop callback BEFORE calling .stop() so the recording
  // pipeline (Whisper + RAG) doesn't keep running in the background
  if (mediaRecorder) {
    mediaRecorder.onstop = null;
    mediaRecorder.ondataavailable = null;
    if (mediaRecorder.state === "recording") {
      try { mediaRecorder.stop(); } catch (_) { }
    }
    mediaRecorder = null;
  }

  // Stop mic tracks immediately — this is what kills the browser’s red mic indicator
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
    mediaStream = null;
  }

  if (audioContext && audioContext.state !== "closed") {
    audioContext.close();
    audioContext = null;
  }
  if (vadAnimationFrame) {
    cancelAnimationFrame(vadAnimationFrame);
    vadAnimationFrame = null;
  }

  voiceModeOverlay.classList.add("hidden");
}

function startVoiceModeListening() {
  voiceModeState = "listening";

  voiceUserSpeech.textContent = "";
  voiceModeOverlay.classList.remove("thinking", "speaking");
  voiceModeOverlay.classList.add("listening");
  voiceStatusText.textContent = "Listening...";

  startRecording();
}

// Event Listeners for Voice Mode Controls
if (voiceModeBtn) {
  voiceModeBtn.addEventListener("click", () => {
    // Unlock browser audio autoplay during this direct user gesture
    unlockAudio();

    stopSpeaking();
    voiceModeState = "listening";

    if (voiceUserSpeech) voiceUserSpeech.textContent = "";
    if (voiceBotSpeech) voiceBotSpeech.textContent = "Hi, I'm listening. Ask me anything about PhD regulations.";

    if (voiceModeOverlay) {
      voiceModeOverlay.classList.remove("hidden");
      voiceModeOverlay.classList.remove("thinking", "speaking");
      voiceModeOverlay.classList.add("listening");
    }
    if (voiceStatusText) voiceStatusText.textContent = "Listening...";

    startRecording();
  });
}

if (exitVoiceModeBtn) exitVoiceModeBtn.addEventListener("click", exitVoiceMode);

const visualizer = document.querySelector(".voice-visualizer");
if (visualizer) {
  visualizer.addEventListener("click", () => {
    if (voiceModeState === "speaking") {
      stopSpeaking();
      startVoiceModeListening();
    } else if (voiceModeState === "listening") {
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
    }
  });
}
// ── PDF Viewer ───────────────────────────────────────────
function openPdfViewer(filename, pageNumber) {
  let modal = document.getElementById("pdfViewerModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "pdfViewerModal";
    modal.className = "pdf-modal";
    modal.innerHTML = `
      <div class="pdf-modal-content">
        <button class="pdf-modal-close" aria-label="Close PDF Viewer">&times;</button>
        <iframe id="pdfViewerIframe" class="pdf-iframe" src="" frameborder="0"></iframe>
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector(".pdf-modal-close").addEventListener("click", () => {
      modal.classList.remove("open");
      document.getElementById("pdfViewerIframe").src = "";
    });

    // Close on outside click
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.classList.remove("open");
        document.getElementById("pdfViewerIframe").src = "";
      }
    });
  }

  const iframe = document.getElementById("pdfViewerIframe");
  // Use #page=N native fragment for PDF
  iframe.src = `/docs/${encodeURIComponent(filename)}#page=${pageNumber}`;
  modal.classList.add("open");
}
