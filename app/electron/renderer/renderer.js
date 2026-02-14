let ws = null;
let authToken = "";
let wsUrl = "";
let activeAudioUrl = null;
let audioContext = null;
let activeSourceNode = null;
let unlockListenersInstalled = false;
let wsConfigKey = "";

const miniOrb = document.getElementById("mini-orb");
const miniExpandBtn = document.getElementById("mini-expand-btn");
const miniOrbVideo = document.getElementById("mini-orb-video");

const widget = document.getElementById("widget-container");
const lobsterChar = document.getElementById("lobster-char");
const stateText = document.getElementById("state-text");
const stateDot = document.getElementById("state-dot");
const statusHint = document.getElementById("status-hint");
const previewBox = document.getElementById("preview-box");
const previewText = document.getElementById("preview-text");
const fullChatModal = document.getElementById("full-chat-modal");
const fullChatLog = document.getElementById("full-chat-log");
const fullChatClose = document.getElementById("full-chat-close");

const input = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const minimizeBtn = document.getElementById("minimize-btn");
const closeBtn = document.getElementById("close-btn");

const history = [];
let streamingBotIndex = -1;
let activeAudio = null;
let isPlayingAudio = false;

const states = {
  idle: "assets/idle.mp4",
  thinking: "assets/thinking.mp4",
  speaking: "assets/speaking.mp4",
  error: "assets/error.mp4",
};

function updateVideo(videoEl, src) {
  if (!videoEl) return;
  if (videoEl.getAttribute("src") !== src) {
    videoEl.setAttribute("src", src);
  }
  videoEl.loop = true;
  try {
    videoEl.currentTime = 0;
  } catch (_e) {}
  videoEl.load();
  videoEl.play().catch(() => {});
}

function setState(state) {
  const src = states[state] || states.idle;
  updateVideo(lobsterChar, src);
  updateVideo(miniOrbVideo, src);
  stateText.textContent = state;
  statusHint.textContent = state;
  if (state === "error") {
    stateDot.style.background = "#dc2626";
  } else if (state === "thinking") {
    stateDot.style.background = "#d97706";
  } else if (state === "speaking") {
    stateDot.style.background = "#7c3aed";
  } else {
    stateDot.style.background = "#22c55e";
  }
}

function stopActiveAudio() {
  if (activeSourceNode) {
    try {
      activeSourceNode.onended = null;
      activeSourceNode.stop(0);
      activeSourceNode.disconnect();
    } catch (_e) {}
    activeSourceNode = null;
  }
  if (activeAudio) {
    try {
      activeAudio.pause();
      activeAudio.src = "";
    } catch (_e) {}
    activeAudio = null;
  }
  if (activeAudioUrl) {
    try {
      URL.revokeObjectURL(activeAudioUrl);
    } catch (_e) {}
    activeAudioUrl = null;
  }
  isPlayingAudio = false;
}

function getAudioContext() {
  if (audioContext) return audioContext;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  audioContext = new Ctx();
  return audioContext;
}

async function unlockAudioContext() {
  const ctx = getAudioContext();
  if (!ctx) return false;
  if (ctx.state === "suspended") {
    try {
      await ctx.resume();
    } catch (err) {
      console.warn("[PET AUDIO] resume() falhou:", err);
      return false;
    }
  }
  return ctx.state === "running";
}

function installAudioUnlockListeners() {
  if (unlockListenersInstalled) return;
  unlockListenersInstalled = true;
  const handler = () => {
    unlockAudioContext();
  };
  ["pointerdown", "click", "keydown", "touchstart"].forEach((ev) => {
    window.addEventListener(ev, handler, { passive: true });
  });
}

function base64ToBytes(raw) {
  try {
    const bin = atob(raw);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) {
      out[i] = bin.charCodeAt(i);
    }
    return out;
  } catch (_e) {
    return null;
  }
}

function bytesToArrayBuffer(bytes) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function bytesToBase64(bytes) {
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return btoa(binary);
}

function normalizeBase64(raw) {
  if (!raw) return "";
  let value = String(raw).trim();
  if (value.startsWith("data:")) {
    const idx = value.indexOf(",");
    value = idx >= 0 ? value.slice(idx + 1) : value;
  }
  value = value.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
  const pad = value.length % 4;
  if (pad) value += "=".repeat(4 - pad);
  return value;
}

async function playPetAudio(base64Data, mimeType = "audio/mpeg") {
  if (!base64Data) return;
  stopActiveAudio();
  const normalized = normalizeBase64(base64Data);
  const bytes = base64ToBytes(normalized);
  if (!bytes || !bytes.length) {
    statusHint.textContent = "Audio invalido recebido.";
    setState("idle");
    return;
  }
  const ctx = getAudioContext();
  if (!ctx) {
    playWithHtmlAudio(bytes, mimeType);
    return;
  }
  await unlockAudioContext();
  const dataBuffer = bytesToArrayBuffer(bytes);
  try {
    const decoded = await ctx.decodeAudioData(dataBuffer.slice(0));
    const source = ctx.createBufferSource();
    source.buffer = decoded;
    source.connect(ctx.destination);
    activeSourceNode = source;
    isPlayingAudio = true;
    statusHint.textContent = `speaking (${mimeType})`;
    setState("speaking");
    source.onended = () => {
      if (activeSourceNode === source) {
        activeSourceNode = null;
      }
      isPlayingAudio = false;
      setState("idle");
    };
    source.start(0);
  } catch (err) {
    console.warn("[PET AUDIO] decodeAudioData falhou, usando fallback:", err);
    playWithHtmlAudio(bytes, mimeType);
  }
}

function attachAudioUnlockOnControls() {
  const unlock = () => unlockAudioContext();
  [miniOrb, miniExpandBtn, sendBtn, input, previewBox, fullChatClose, minimizeBtn, closeBtn]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("click", unlock);
      el.addEventListener("keydown", unlock);
    });
}

function clearAudioStateAfterFallback(audio) {
  isPlayingAudio = false;
  if (activeAudio === audio) {
    activeAudio = null;
  }
  if (activeAudioUrl) {
    try {
      URL.revokeObjectURL(activeAudioUrl);
    } catch (_e) {}
    activeAudioUrl = null;
  }
}

function legacyCleanupOnEnded(audio) {
  audio.addEventListener("ended", () => {
    clearAudioStateAfterFallback(audio);
    setState("idle");
  });
  audio.addEventListener("error", () => {
    clearAudioStateAfterFallback(audio);
    setState("idle");
  });
  audio.play().catch((err) => {
    clearAudioStateAfterFallback(audio);
    const msg = err && err.message ? err.message : "Falha ao tocar audio no pet.";
    console.error("[PET AUDIO] play() error:", err);
    statusHint.textContent = msg;
    setState("idle");
  });
}

function playWithHtmlAudio(bytes, mimeType) {
  let audioSrc = "";
  try {
    const blob = new Blob([bytes], { type: mimeType });
    activeAudioUrl = URL.createObjectURL(blob);
    audioSrc = activeAudioUrl;
  } catch (_e) {
    const normalized = normalizeBase64(bytesToBase64(bytes));
    audioSrc = `data:${mimeType};base64,${normalized}`;
  }
  const audio = new Audio(audioSrc);
  audio.preload = "auto";
  audio.muted = false;
  audio.volume = 1.0;
  activeAudio = audio;
  isPlayingAudio = true;
  statusHint.textContent = `speaking (${mimeType})`;
  setState("speaking");
  legacyCleanupOnEnded(audio);
}

function showBubble() {
  closeFullChat();
  widget.style.display = "none";
  miniOrb.style.display = "flex";
  window.deskpet.minimizeWindow();
}

function showPanel() {
  miniOrb.style.display = "none";
  widget.style.display = "";
  window.deskpet.restoreWindow();
}

function updatePreview() {
  if (!previewText) return;
  const last = history[history.length - 1];
  if (!last || !last.text) {
    previewText.textContent = "Conversa completa";
    return;
  }
  const text = String(last.text).replace(/\s+/g, " ").trim();
  previewText.textContent = text.length > 110 ? `${text.slice(0, 110)}...` : text;
}

function renderFullChat() {
  if (!fullChatLog) return;
  fullChatLog.innerHTML = "";
  for (const item of history) {
    const div = document.createElement("div");
    div.className = `chat-msg ${item.role}`;
    div.textContent = item.text;
    fullChatLog.appendChild(div);
  }
  fullChatLog.scrollTop = fullChatLog.scrollHeight;
}

function openFullChat() {
  renderFullChat();
  fullChatModal.classList.remove("hidden");
}

function closeFullChat() {
  fullChatModal.classList.add("hidden");
}

function connect() {
  if (!wsUrl || !authToken) return;
  const nextKey = `${wsUrl}|${authToken}`;
  if (
    ws &&
    wsConfigKey === nextKey &&
    (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  if (ws) {
    try {
      ws.__intentionalClose = true;
      ws.close(1000, "reconnect");
    } catch (_e) {}
  }

  wsConfigKey = nextKey;
  const socket = new WebSocket(wsUrl);
  ws = socket;

  socket.addEventListener("open", () => {
    if (ws !== socket) return;
    socket.send(JSON.stringify({ type: "auth", token: authToken }));
  });
  socket.addEventListener("message", (ev) => {
    if (ws !== socket) return;
    const data = JSON.parse(ev.data);
    if (data.type === "state") {
      setState(data.value);
      return;
    }
    if (data.type === "delta") {
      if (streamingBotIndex < 0) {
        history.push({ role: "bot", text: "" });
        streamingBotIndex = history.length - 1;
      }
      history[streamingBotIndex].text += data.text;
      updatePreview();
      if (!fullChatModal.classList.contains("hidden")) {
        renderFullChat();
      }
      return;
    }
    if (data.type === "audio") {
      void playPetAudio(data.base64, data.mime || "audio/mpeg");
      return;
    }
    if (data.type === "audio_error") {
      statusHint.textContent = data.message || "Falha ao gerar audio no pet.";
      return;
    }
    if (data.type === "done") {
      streamingBotIndex = -1;
      return;
    }
  });
  socket.addEventListener("close", () => {
    if (ws !== socket) return;
    if (socket.__intentionalClose) return;
    stopActiveAudio();
    setState("error");
  });
}

function sendMessage() {
  const text = input.value.trim();
  if (!text || !ws) return;
  unlockAudioContext();
  stopActiveAudio();
  input.value = "";
  history.push({ role: "user", text });
  updatePreview();
  if (!fullChatModal.classList.contains("hidden")) {
    renderFullChat();
  }
  streamingBotIndex = -1;
  setState("thinking");
  ws.send(JSON.stringify({ type: "user_message", text }));
}

miniOrb.addEventListener("click", showPanel);
miniExpandBtn.addEventListener("click", showPanel);

sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});
previewBox.addEventListener("click", openFullChat);
fullChatClose.addEventListener("click", closeFullChat);
fullChatModal.addEventListener("click", (e) => {
  if (e.target === fullChatModal) closeFullChat();
});

minimizeBtn.addEventListener("click", showBubble);
if (closeBtn) {
  closeBtn.addEventListener("click", () => window.deskpet.closeWindow());
}

window.deskpet.onBackendConfig((cfg) => {
  const nextUrl = cfg.url || "";
  const nextToken = cfg.token || "";
  const sameConfig = nextUrl === wsUrl && nextToken === authToken;
  wsUrl = nextUrl;
  authToken = nextToken;
  if (
    sameConfig &&
    ws &&
    (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }
  connect();
});

window.deskpet.onMiniMode((isMini) => {
  if (isMini) {
    widget.style.display = "none";
    miniOrb.style.display = "flex";
  } else {
    miniOrb.style.display = "none";
    widget.style.display = "";
  }
});

setState("idle");
updatePreview();
installAudioUnlockListeners();
attachAudioUnlockOnControls();
showBubble();
