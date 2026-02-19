/* ══════════════════════════════════════════════════════
   AVA – Voice Agent  |  app.js
   ══════════════════════════════════════════════════════ */

const BACKEND_WS = "ws://localhost:8000/agent/proxy";

// ── DOM ────────────────────────────────────────────────
const orbWrap = document.getElementById("orb-wrap");
const lblMain = document.getElementById("lbl-main");
const lblSub = document.getElementById("lbl-sub");
const callBtn = document.getElementById("call-btn");
const callHint = document.getElementById("call-hint");
const btnLog = document.getElementById("btn-log");
const logPanel = document.getElementById("log");
const logScroll = document.getElementById("log-scroll");
const sdot = document.getElementById("sdot");
const statusTxt = document.getElementById("status-txt");
const toasts = document.getElementById("toasts");

// ── State machine ──────────────────────────────────────
const STATES = {
  idle: { label: "Ready to call", sub: "Tap the button below to start", dot: "", hint: "Start conversation" },
  connecting: { label: "Connecting…", sub: "Setting up your session", dot: "act", hint: "Connecting…" },
  listening: { label: "Listening", sub: "Go ahead, speak naturally", dot: "act", hint: "Tap to end call" },
  user_speaking: { label: "Hearing you…", sub: "", dot: "act", hint: "Tap to end call" },
  thinking: { label: "Thinking…", sub: "", dot: "act", hint: "Tap to end call" },
  agent_speaking: { label: "AVA is speaking", sub: "Tap End to interrupt", dot: "act", hint: "Tap to end call" },
};

let curState = "idle";

function setState(s) {
  curState = s;
  const cfg = STATES[s] || STATES.idle;
  orbWrap.dataset.state = s;
  lblMain.textContent = cfg.label;
  lblSub.textContent = cfg.sub;
  callHint.textContent = cfg.hint;
  sdot.className = "sdot " + cfg.dot;
  statusTxt.textContent = cfg.label;

  const active = s !== "idle";
  callBtn.className = "call-btn " + (active ? "active" : "idle");
  callBtn.setAttribute("aria-label", active ? "End call" : "Start call");
}

// ── Audio: PCM player (Int16 @24 kHz) ─────────────────
const OUT_HZ = 24000;
let playCtx = null;
let nextAt = 0;

function ensurePlayCtx() {
  if (!playCtx || playCtx.state === "closed") {
    playCtx = new AudioContext({ sampleRate: OUT_HZ });
    nextAt = 0;
  }
  if (playCtx.state === "suspended") playCtx.resume();
}

function playChunk(arrayBuffer) {
  ensurePlayCtx();
  const i16 = new Int16Array(arrayBuffer);
  const f32 = new Float32Array(i16.length);
  for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;

  const buf = playCtx.createBuffer(1, f32.length, OUT_HZ);
  buf.copyToChannel(f32, 0);
  const src = playCtx.createBufferSource();
  src.buffer = buf;
  src.connect(playCtx.destination);
  const now = playCtx.currentTime;
  const when = Math.max(now + 0.008, nextAt);
  src.start(when);
  nextAt = when + buf.duration;
}

function flushAudio() {
  if (playCtx) { try { playCtx.close(); } catch (_) { } }
  playCtx = null;
  nextAt = 0;
}

// ── Audio: mic capture (Float32→Int16 @48 kHz) ────────
const IN_HZ = 48000;
let captureCtx = null, micStream = null, processor = null;

async function startMic(ws) {
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, sampleRate: IN_HZ, echoCancellation: true, noiseSuppression: true }
  });
  captureCtx = new AudioContext({ sampleRate: IN_HZ });
  const src = captureCtx.createMediaStreamSource(micStream);
  processor = captureCtx.createScriptProcessor(2048, 1, 1);
  processor.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    ws.send(i16.buffer);
  };
  src.connect(processor);
  processor.connect(captureCtx.destination);
}

function stopMic() {
  if (processor) { processor.disconnect(); processor = null; }
  if (captureCtx) { captureCtx.close(); captureCtx = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
}

// ── WebSocket session ──────────────────────────────────
let agentWs = null;

async function startCall() {
  setState("connecting");
  agentWs = new WebSocket(BACKEND_WS);
  agentWs.binaryType = "arraybuffer";

  agentWs.onopen = async () => {
    toast("Session open — starting mic…", "info", 2000);
    try {
      await startMic(agentWs);
    } catch (e) {
      toast(`Mic error: ${e.message}`, "error");
      hangup();
    }
  };

  agentWs.onerror = () => {
    toast("Cannot reach AVA server — is it running?", "error");
    hangup();
  };

  agentWs.onclose = () => {
    if (curState !== "idle") hangup();
  };

  agentWs.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      // Binary = agent speech PCM
      playChunk(ev.data);
    } else {
      // Text = JSON event from Deepgram
      try { handleEvent(JSON.parse(ev.data)); } catch (_) { }
    }
  };
}

function hangup() {
  stopMic();
  flushAudio();
  if (agentWs) {
    try { agentWs.close(); } catch (_) { }
    agentWs = null;
  }
  setState("idle");
  sdot.className = "sdot";
  statusTxt.textContent = "Offline";
}

// ── Deepgram event handler ─────────────────────────────
function handleEvent(msg) {
  switch (msg.type) {
    case "SettingsApplied":
      setState("listening");
      toast("Connected ✓", "success", 2500);
      break;

    case "UserStartedSpeaking":
      setState("user_speaking");
      flushAudio();          // interrupt agent mid-sentence
      break;

    case "AgentThinking":
      setState("thinking");
      break;

    case "AgentStartedSpeaking":
      setState("agent_speaking");
      break;

    case "AgentAudioDone":
      if (curState === "agent_speaking") setState("listening");
      break;

    case "ConversationText":
      addTranscript(msg.role, msg.content);
      break;

    case "Welcome":
      // Deepgram sends this before SettingsApplied sometimes
      break;

    case "Error":
      toast(`Agent error: ${msg.description || JSON.stringify(msg)}`, "error");
      break;

    default:
      console.debug("Agent event:", msg);
  }
}

// ── Transcript ─────────────────────────────────────────
function addTranscript(role, content) {
  if (!content?.trim()) return;
  const empty = logScroll.querySelector(".log-empty");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = `log-msg ${role === "user" ? "user" : "agent"}`;
  div.innerHTML = `<span class="role">${role === "user" ? "You" : "AVA"}</span>
                   <span class="content">${escHTML(content)}</span>`;
  logScroll.appendChild(div);
  logScroll.scrollTop = logScroll.scrollHeight;

  // Auto-show transcript on first message
  logPanel.classList.remove("hidden");
}

function escHTML(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── UI bindings ────────────────────────────────────────
callBtn.addEventListener("click", () => {
  if (curState === "idle") {
    startCall().catch(e => { toast(e.message, "error"); setState("idle"); });
  } else {
    hangup();
  }
});

btnLog.addEventListener("click", () => logPanel.classList.toggle("hidden"));

// ── Toast ──────────────────────────────────────────────
function toast(msg, type = "info", ms = 4000) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  toasts.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

// ── Boot: health check ─────────────────────────────────
(async function boot() {
  try {
    const r = await fetch("http://localhost:8000/health");
    const d = await r.json();
    sdot.className = "sdot on";
    statusTxt.textContent = d.ollama_running ? "Ready" : "Ollama offline";
    if (!d.ollama_running) toast("⚠ Ollama not running — start with: ollama serve", "error", 6000);
  } catch {
    statusTxt.textContent = "Server offline";
    toast("Start backend: python main.py", "error", 6000);
  }
  setInterval(async () => {
    try {
      const r = await fetch("http://localhost:8000/health");
      const d = await r.json();
      sdot.className = "sdot on";
      statusTxt.textContent = "Ready";
    } catch {
      if (curState === "idle") { sdot.className = "sdot err"; statusTxt.textContent = "Server offline"; }
    }
  }, 30_000);
})();
