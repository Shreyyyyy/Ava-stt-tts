/* ══════════════════════════════════════════════════════
   AVA – Sarvam AI Voice Interface  |  app.js
   ══════════════════════════════════════════════════════ */

const BACKEND_API = "http://localhost:8000";

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
  idle: { label: "Ready", sub: "Select language and enter text", dot: "", hint: "Start voice session" },
  processing: { label: "Processing…", sub: "Converting text to speech", dot: "act", hint: "Processing…" },
  playing: { label: "Speaking", sub: "Playing generated audio", dot: "act", hint: "Tap to stop" },
  recording: { label: "Recording…", sub: "Speak clearly", dot: "rec", hint: "Stop recording" },
  transcribing: { label: "Transcribing…", sub: "Converting speech to text", dot: "act", hint: "Processing…" },
};

let curState = "idle";
let mediaRecorder = null;
let audioChunks = [];

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
  callBtn.setAttribute("aria-label", active ? "Stop" : "Start");
}

// ── Audio playback ─────────────────────────────────────────
let currentAudio = null;

function playAudio(audioBlob) {
  const audioUrl = URL.createObjectURL(audioBlob);
  
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
  }
  
  currentAudio = new Audio(audioUrl);
  currentAudio.play();
  
  currentAudio.onended = () => {
    URL.revokeObjectURL(audioUrl);
    setState("idle");
  };
  
  currentAudio.onerror = () => {
    URL.revokeObjectURL(audioUrl);
    toast("Audio playback error", "error");
    setState("idle");
  };
}

function stopAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
  setState("idle");
}

// ── Audio recording ─────────────────────────────────────────
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: { 
        channelCount: 1, 
        sampleRate: 16000,
        echoCancellation: true, 
        noiseSuppression: true 
      } 
    });
    
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    audioChunks = [];
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };
    
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      await transcribeAudio(audioBlob);
      stream.getTracks().forEach(track => track.stop());
    };
    
    mediaRecorder.start();
    setState("recording");
    toast("Recording started", "info", 2000);
    
  } catch (error) {
    toast(`Microphone error: ${error.message}`, "error");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    setState("transcribing");
  }
}

// ── Voice Call State ─────────────────────────────────────────
let callState = 'idle'; // idle, calling, speaking, processing
let callMediaRecorder = null;
let callStream = null;
let callAudioChunks = [];
let isProcessingResponse = false;
let currentAudio = null; // Track currently playing audio (declared globally)
let interruptionDetection = null;

// ── Voice Call Functions ─────────────────────────────────────────

async function startVoiceCall() {
  if (callState !== 'idle') return;
  
  try {
    callState = 'calling';
    updateCallUI();
    
    // Start interruption detection
    startInterruptionDetection();
    
    // Start recording
    callAudioChunks = [];
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: { 
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 16000 
      } 
    });
    
    callStream = stream;
    callMediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    });
    
    callMediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        callAudioChunks.push(event.data);
      }
    };
    
    callMediaRecorder.onstop = async () => {
      if (callAudioChunks.length > 0 && !isProcessingResponse) {
        await processVoiceInput();
      }
    };
    
    callMediaRecorder.start(1000); // Record in 1-second chunks
    toast("📞 Call started - Speak now!", "success", 2000);
    
  } catch (error) {
    console.error('Call start error:', error);
    toast(`Microphone error: ${error.message}`, "error");
    endVoiceCall();
  }
}

function startInterruptionDetection() {
  // Monitor microphone levels during AVA's speech
  if (callStream) {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(callStream);
    const analyser = audioContext.createAnalyser();
    
    source.connect(analyser);
    analyser.fftSize = 256;
    
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    interruptionDetection = setInterval(() => {
      if (callState === 'speaking') {
        analyser.getByteFrequencyData(dataArray);
        
        // Calculate average volume
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const average = sum / bufferLength;
        
        // If user speaks (volume above threshold), interrupt
        if (average > 30) { // Threshold for speech detection
          handleInterruption();
        }
      }
    }, 100); // Check every 100ms
  }
}

function handleInterruption() {
  if (callState === 'speaking') {
    console.log('User interrupted AVA');
    
    // Stop current audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    
    // Stop processing
    isProcessingResponse = false;
    
    // Immediately switch to listening
    callState = 'calling';
    updateCallUI();
    
    // Resume recording immediately
    if (callMediaRecorder && callMediaRecorder.state === 'inactive') {
      callMediaRecorder.start(1000);
    }
    
    toast("🗣 Interrupting - Listening now", "info", 1500);
    addTranscript("system", "You interrupted AVA");
  }
}

async function processVoiceInput() {
  if (isProcessingResponse) return;
  isProcessingResponse = true;
  
  try {
    callState = 'processing';
    updateCallUI();
    
    // Stop recording temporarily
    if (callMediaRecorder && callMediaRecorder.state === 'recording') {
      callMediaRecorder.stop();
    }
    
    // Create audio blob
    const audioBlob = new Blob(callAudioChunks, { type: 'audio/webm' });
    callAudioChunks = []; // Reset for next recording
    
    // Transcribe with Sarvam AI
    const transcript = await transcribeVoiceInput(audioBlob);
    
    if (transcript && transcript.trim()) {
      addTranscript("user", transcript);
      
      // Generate LLM response
      const response = await generateLLMResponse(transcript);
      
      if (response) {
        addTranscript("agent", response);
        
        // Convert to speech
        await speakResponse(response);
      }
    }
    
  } catch (error) {
    console.error('Voice processing error:', error);
    toast(`Processing error: ${error.message}`, "error");
  } finally {
    isProcessingResponse = false;
    if (callState === 'processing') {
      callState = 'calling';
      updateCallUI();
      // Resume recording for next input
      if (callMediaRecorder && callMediaRecorder.state === 'inactive') {
        callMediaRecorder.start(1000);
      }
    }
  }
}

async function transcribeVoiceInput(audioBlob) {
  try {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, `call_${Date.now()}.webm`);
    formData.append('language_code', 'hi-IN');
    formData.append('model', 'saaras:v3');
    
    const response = await fetch(`${BACKEND_API}/sarvam/stt/upload`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('Transcription failed');
    }
    
    const result = await response.json();
    return result.transcript || "Transcription unclear";
    
  } catch (error) {
    console.error('Transcription error:', error);
    return "Transcription failed";
  }
}

async function generateLLMResponse(transcript) {
  try {
    const response = await fetch(`${BACKEND_API}/ava/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: transcript,
        language_code: 'hi-IN',
        speaker: 'shreya'
      })
    });
    
    if (!response.ok) {
      throw new Error('LLM generation failed');
    }
    
    const audioBlob = await response.blob();
    await playAudioWithInterruption(audioBlob);
    
    // Return a placeholder since we don't have the actual text
    return "🤖 AVA responded with voice";
    
  } catch (error) {
    console.error('LLM error:', error);
    return "I'm having trouble responding right now.";
  }
}

async function playAudioWithInterruption(audioBlob) {
  return new Promise((resolve) => {
    callState = 'speaking';
    updateCallUI();
    
    const audio = new Audio(URL.createObjectURL(audioBlob));
    currentAudio = audio;
    
    audio.onended = () => {
      currentAudio = null;
      resolve();
    };
    
    audio.onerror = () => {
      currentAudio = null;
      console.error('Audio playback error');
      resolve();
    };
    
    audio.play().catch(error => {
      console.error('Audio play error:', error);
      currentAudio = null;
      resolve();
    });
  });
}

async function speakResponse(text) {
  // This function is now handled by playAudioWithInterruption
  callState = 'speaking';
  updateCallUI();
  
  try {
    // Resume listening after response (if not interrupted)
    setTimeout(() => {
      if (callState === 'speaking' && !isProcessingResponse) {
        callState = 'calling';
        updateCallUI();
        if (callMediaRecorder && callMediaRecorder.state === 'inactive') {
          callMediaRecorder.start(1000);
        }
      }
    }, 1000); // Shorter delay to allow interruption
    
  } catch (error) {
    console.error('Speech error:', error);
  }
}

function endVoiceCall() {
  callState = 'idle';
  updateCallUI();
  
  // Stop interruption detection
  if (interruptionDetection) {
    clearInterval(interruptionDetection);
    interruptionDetection = null;
  }
  
  // Stop current audio
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  
  // Stop recording
  if (callMediaRecorder && callMediaRecorder.state !== 'inactive') {
    callMediaRecorder.stop();
  }
  
  // Stop media stream
  if (callStream) {
    callStream.getTracks().forEach(track => track.stop());
    callStream = null;
  }
  
  // Cleanup
  callMediaRecorder = null;
  callAudioChunks = [];
  isProcessingResponse = false;
  
  toast("📞 Call ended", "info", 2000);
}

function updateCallUI() {
  const startBtn = document.getElementById('start-call-btn');
  const endBtn = document.getElementById('end-call-btn');
  const statusIcon = document.querySelector('.status-icon');
  const statusText = document.querySelector('.status-text');
  
  switch (callState) {
    case 'idle':
      startBtn.style.display = 'flex';
      endBtn.style.display = 'none';
      statusIcon.textContent = '📞';
      statusText.textContent = 'Ready to start call';
      break;
      
    case 'calling':
      startBtn.style.display = 'none';
      endBtn.style.display = 'flex';
      statusIcon.textContent = '🎤';
      statusText.textContent = 'Listening...';
      statusIcon.style.color = '#10b981';
      break;
      
    case 'processing':
      startBtn.style.display = 'none';
      endBtn.style.display = 'flex';
      statusIcon.textContent = '⚡';
      statusText.textContent = 'Processing...';
      statusIcon.style.color = '#f59e0b';
      break;
      
    case 'speaking':
      startBtn.style.display = 'none';
      endBtn.style.display = 'flex';
      statusIcon.textContent = '🔊';
      statusText.textContent = 'AVA speaking...';
      statusIcon.style.color = '#8b5cf6';
      break;
  }
}

async function generateSpeech(text, language, speaker) {
  setState("processing");
  
  try {
    const response = await fetch(`${BACKEND_API}/sarvam/tts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: text,
        target_language_code: language,
        speaker: speaker,
        model: "bulbul:v3"
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'TTS failed');
    }

    const audioBlob = await response.blob();
    playAudio(audioBlob);
    addTranscript("agent", text);
    
  } catch (error) {
    toast(`Speech generation error: ${error.message}`, "error");
    setState("idle");
  }
}

async function transcribeAudio(audioBlob) {
  try {
    setState("transcribing");
    
    // Convert blob to file
    const audioFile = new File([audioBlob], `recording_${Date.now()}.webm`, { type: 'audio/webm' });
    
    // Create FormData for file upload
    const formData = new FormData();
    formData.append('audio_file', audioFile);
    formData.append('language_code', document.getElementById('stt-language').value);
    formData.append('model', 'saaras:v3');
    formData.append('with_diarization', 'true');
    
    toast("Uploading and transcribing audio...", "info", 3000);
    
    const response = await fetch(`${BACKEND_API}/sarvam/stt/upload`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'STT upload failed');
    }
    
    const result = await response.json();
    
    if (result.status === 'completed') {
      addTranscript("user", result.transcript || "Transcription completed");
      toast("✅ Transcription completed successfully", "success", 3000);
    } else {
      throw new Error('Transcription failed');
    }
    
  } catch (error) {
    console.error('Transcription error:', error);
    toast(`Transcription error: ${error.message}`, "error");
  } finally {
    setState("idle");
  }
}

async function loadLanguages() {
  try {
    const [ttsResponse, sttResponse] = await Promise.all([
      fetch(`${BACKEND_API}/sarvam/tts/languages`),
      fetch(`${BACKEND_API}/sarvam/stt/languages`)
    ]);

    const ttsData = await ttsResponse.json();
    const sttData = await sttResponse.json();

    // Populate language selectors
    const ttsSelect = document.getElementById('tts-language');
    const sttSelect = document.getElementById('stt-language');
    const chatSelect = document.getElementById('chat-language');

    Object.entries(ttsData.languages).forEach(([code, name]) => {
      const option = new Option(name, code);
      ttsSelect.add(option);
      chatSelect.add(option.cloneNode(true));
    });

    Object.entries(sttData.languages).forEach(([code, name]) => {
      const option = new Option(name, code);
      sttSelect.add(option);
    });

  } catch (error) {
    console.error('Failed to load languages:', error);
  }
}

async function loadSpeakers() {
  try {
    const response = await fetch(`${BACKEND_API}/sarvam/tts/speakers`);
    const data = await response.json();

    const speakerSelect = document.getElementById('tts-speaker');
    const chatSpeakerSelect = document.getElementById('chat-speaker');
    
    Object.entries(data.speakers).forEach(([id, description]) => {
      const option = new Option(description, id);
      speakerSelect.add(option);
      chatSpeakerSelect.add(option.cloneNode(true));
    });

  } catch (error) {
    console.error('Failed to load speakers:', error);
  }
}

async function sendChatMessage() {
  const message = document.getElementById('chat-message').value.trim();
  const language = document.getElementById('chat-language').value;
  const speaker = document.getElementById('chat-speaker').value;
  
  if (!message) {
    toast("Please enter a message", "warning");
    return;
  }
  
  setState("processing");
  addTranscript("user", message);
  
  try {
    const response = await fetch(`${BACKEND_API}/ava/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        language_code: language,
        speaker: speaker,
        model: "bulbul:v3"
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Chat request failed');
    }

    const audioBlob = await response.blob();
    playAudio(audioBlob);
    
    // Clear message input
    document.getElementById('chat-message').value = '';
    
    // Add AVA's response to transcript (we don't know the exact text, but we can indicate it was generated)
    const responseType = response.headers.get('X-Response-Type');
    if (responseType === 'llm_generated') {
      addTranscript("agent", "🤖 AVA responded with AI-generated speech");
    } else {
      addTranscript("agent", "🔊 AVA responded with a preset message");
    }
    
  } catch (error) {
    toast(`Chat error: ${error.message}`, "error");
    setState("idle");
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

  logPanel.classList.remove("hidden");
}

function escHTML(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── UI bindings ───────────────────────────────────────
callBtn.addEventListener("click", () => {
  if (curState === "idle") {
    const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
    
    if (activeTab === 'tts') {
      const text = document.getElementById('tts-text').value.trim();
      const language = document.getElementById('tts-language').value;
      const speaker = document.getElementById('tts-speaker').value;
      
      if (!text) {
        toast("Please enter text to convert", "warning");
        return;
      }
      
      generateSpeech(text, language, speaker);
    } else if (activeTab === 'stt') {
      startRecording();
    } else if (activeTab === 'chat') {
      // Check if voice call is available
      if (callState === 'idle') {
        startVoiceCall();
      } else {
        endVoiceCall();
      }
    }
  } else if (curState === "recording") {
    stopRecording();
  } else if (curState === "playing") {
    stopAudio();
  }
});

// Voice call button bindings
document.getElementById('start-call-btn')?.addEventListener('click', startVoiceCall);
document.getElementById('end-call-btn')?.addEventListener('click', endVoiceCall);

// Fallback text send
document.getElementById('send-text-btn')?.addEventListener('click', () => {
  const message = document.getElementById('chat-message').value.trim();
  if (message) {
    sendChatMessage();
  }
});

btnLog.addEventListener("click", () => logPanel.classList.toggle("hidden"));

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    btn.classList.add('active');
    document.getElementById(`${btn.dataset.tab}-tab`).classList.add('active');
    
    // Update button text and hint
    const activeTab = btn.dataset.tab;
    if (activeTab === 'tts') {
      callHint.textContent = 'Generate speech';
      lblSub.textContent = 'Select language and enter text';
    } else if (activeTab === 'stt') {
      callHint.textContent = 'Start recording';
      lblSub.textContent = 'Select language and click to record';
    } else if (activeTab === 'chat') {
      callHint.textContent = callState === 'idle' ? 'Start Call' : 'End Call';
      lblSub.textContent = 'Click to start voice conversation';
    }
  });
});

// Enter key support for chat
document.getElementById('chat-message')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
});

// ── Toast ──────────────────────────────────────────────
function toast(msg, type = "info", ms = 4000) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  toasts.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

// ── Boot: health check and initialization ─────────────────────────────────
(async function boot() {
  try {
    const r = await fetch(`${BACKEND_API}/health`);
    const d = await r.json();
    sdot.className = "sdot on";
    statusTxt.textContent = d.sarvam_tts_available && d.sarvam_stt_available && d.ollama_available ? "Ready" : "Partial";
    
    if (!d.sarvam_tts_available || !d.sarvam_stt_available) {
      toast("⚠ Some Sarvam services unavailable", "warning", 5000);
    }
    
    if (!d.ollama_available) {
      toast("⚠ Ollama not available. Voice assistant will use preset responses.", "warning", 5000);
    }
    
    // Load languages and speakers
    await Promise.all([loadLanguages(), loadSpeakers()]);
    
  } catch {
    statusTxt.textContent = "Server offline";
    toast("Start backend: python -m uvicorn backend.server:app", "error", 6000);
  }
  
  // Periodic health check
  setInterval(async () => {
    try {
      const r = await fetch(`${BACKEND_API}/health`);
      const d = await r.json();
      sdot.className = "sdot on";
      statusTxt.textContent = d.sarvam_tts_available && d.sarvam_stt_available && d.ollama_available ? "Ready" : "Partial";
    } catch {
      if (curState === "idle") { 
        sdot.className = "sdot err"; 
        statusTxt.textContent = "Server offline"; 
      }
    }
  }, 30_000);
})();
