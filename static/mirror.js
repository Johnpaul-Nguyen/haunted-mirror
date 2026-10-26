// Haunted Mirror front end: reflection, ghost, voice in and out, talking to the server.

const L = window.MirrorLogic;
const $ = (s) => document.querySelector(s);
const body = document.body;
const input = $("#say");
const words = $("#words");
const heard = $("#heard");
const mic = $("#mic");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let state = "veiled";
let busy = false;
let cameraOn = false;
let present = false;
let seenSinceSummon = false;
let cooldownUntil = 0;
let mode = "";
let lastViaVoice = false;

// ---------- sound (synthesised, no files) ----------

const sound = (() => {
  let ctx, master, drone;

  function noise(seconds) {
    const buf = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  return {
    unlock() {
      if (ctx) return;
      ctx = new AudioContext();
      master = ctx.createGain();
      master.gain.value = 0.8;
      master.connect(ctx.destination);
      drone = ctx.createGain();
      drone.gain.value = 0;
      drone.connect(master);
      const bp = ctx.createBiquadFilter();
      bp.type = "bandpass";
      bp.frequency.value = 420;
      bp.Q.value = 0.8;
      bp.connect(drone);
      const wind = ctx.createBufferSource();
      wind.buffer = noise(4);
      wind.loop = true;
      const windGain = ctx.createGain();
      windGain.gain.value = 0.25;
      wind.connect(windGain).connect(bp);
      wind.start();
      for (const f of [110, 110.7, 164.8]) {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = "sine";
        o.frequency.value = f;
        g.gain.value = 0.12;
        o.connect(g).connect(drone);
        o.start();
      }
      const lfo = ctx.createOscillator();
      const depth = ctx.createGain();
      lfo.frequency.value = 0.09;
      depth.gain.value = 250;
      lfo.connect(depth).connect(bp.frequency);
      lfo.start();
    },
    level(v) {
      if (ctx) drone.gain.setTargetAtTime(v, ctx.currentTime, 1.2);
    },
    screech() {
      if (!ctx) return;
      const t = ctx.currentTime;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.45, t + 0.03);
      g.gain.exponentialRampToValueAtTime(0.001, t + 1.0);
      g.connect(master);
      for (const detune of [0, 23, 51]) {
        const o = ctx.createOscillator();
        o.type = "sawtooth";
        o.frequency.setValueAtTime(900 + detune, t);
        o.frequency.exponentialRampToValueAtTime(2900 + detune * 8, t + 0.25);
        o.frequency.exponentialRampToValueAtTime(600, t + 1.0);
        o.connect(g);
        o.start(t);
        o.stop(t + 1.05);
      }
      const hiss = ctx.createBufferSource();
      hiss.buffer = noise(1);
      hiss.connect(g);
      hiss.start(t);
    },
  };
})();

// ---------- voice out ----------

const support = L.speechSupport(window);
let voice = null;
if (support.speak) {
  const load = () => { voice = L.pickVoice(speechSynthesis.getVoices()); };
  load();
  speechSynthesis.onvoiceschanged = load;
}

function speak(text) {
  return new Promise((resolve) => {
    const clean = L.cleanForSpeech(text);
    if (!support.speak || !clean) return resolve();
    const u = new SpeechSynthesisUtterance(clean);
    if (voice) u.voice = voice;
    u.rate = 0.86;
    u.pitch = body.dataset.mood === "care" ? 1 : 0.55;
    let timer;
    const done = () => { clearTimeout(timer); resolve(); };
    timer = setTimeout(done, L.speakTimeout(clean));
    u.onend = done;
    u.onerror = done;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  });
}

// ---------- voice in ----------

let voiceOk = support.listen;
let rec = null;
let listening = false;

function note(text) { $("#voicenote").textContent = text; }

function updateMic() {
  mic.hidden = !voiceOk;
  mic.disabled = busy || state !== "awake";
  mic.classList.toggle("listening", listening);
  renderHud();
}

function listen() {
  if (!voiceOk || listening || busy || state !== "awake") return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  let finalText = "";
  rec.onresult = (e) => {
    let interim = "";
    finalText = "";
    for (const r of e.results) {
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    input.value = finalText || interim;
  };
  rec.onerror = (e) => {
    const msg = L.voiceError(e.error);
    if (msg) {
      note(msg);
      voiceOk = false; // stop retrying a broken mic; typing still works
    }
  };
  rec.onend = () => {
    listening = false;
    updateMic();
    const text = finalText.trim();
    if (text) {
      lastViaVoice = true;
      send(text);
    } else {
      input.value = "";
    }
  };
  try {
    rec.start();
    listening = true;
    note("");
  } catch {
    note(L.voiceError("start-failed"));
    voiceOk = false;
  }
  updateMic();
}

function toggleListen() {
  if (listening) rec && rec.stop();
  else listen();
}

// ---------- the ghost's words ----------

async function typeWords(text) {
  words.textContent = "";
  for (let i = 1; i <= text.length; i++) {
    words.textContent = text.slice(0, i);
    await sleep(text[i - 1] === "." ? 140 : 24);
  }
}

function setInput(on) {
  input.disabled = !on;
  if (on) input.focus();
  updateMic();
}

async function show(reply) {
  busy = true;
  setInput(false);
  body.dataset.mood = reply.mood || "calm";
  await Promise.all([typeWords(reply.say || "..."), speak(reply.say || "")]);
  busy = false;
  if (reply.bye) {
    await sleep(1500);
    goToSleep(true);
    return;
  }
  setInput(true);
  if (lastViaVoice) listen();
}

async function post(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  });
  if (!res.ok) throw new Error(res.status);
  return res.json();
}

async function send(text) {
  if (busy || state !== "awake") return;
  heard.textContent = `you: ${text}`;
  input.value = "";
  busy = true;
  setInput(false);
  words.textContent = "...";
  let reply;
  try {
    reply = await post("/api/say", { text });
  } catch {
    reply = { say: "The glass has gone silent. (The server can't be reached.)", mood: "ominous" };
  }
  busy = false;
  await show(reply);
}

// ---------- visits ----------

async function scare() {
  sound.screech();
  $("#scarer").classList.add("on");
  body.classList.add("shake");
  await sleep(1000);
  $("#scarer").classList.remove("on");
  body.classList.remove("shake");
}

async function summon(manual) {
  if (busy || L.next(state, manual ? "manual" : "face") !== "summoning") return;
  state = "summoning";
  busy = true;
  seenSinceSummon = !manual;
  lastViaVoice = false;
  body.classList.remove("asleep");
  heard.textContent = "";
  words.textContent = "";
  await scare();
  sound.level(0.3);
  let reply;
  try {
    reply = await post("/api/summon");
  } catch {
    reply = { say: "The glass will not clear. Is the server running?", mood: "ominous" };
  }
  state = L.next(state, "summoned");
  busy = false;
  await show(reply);
}

function goToSleep(afterBye) {
  if (listening && rec) rec.abort();
  if (support.speak) speechSynthesis.cancel();
  state = L.next(L.next(state, "bye"), "slept");
  busy = false;
  body.classList.add("asleep");
  body.dataset.mood = "calm";
  input.value = "";
  setInput(false);
  sound.level(0.1);
  if (afterBye) cooldownUntil = Date.now() + 15000;
  setSleepText();
}

async function depart() {
  state = L.next(state, "left");
  busy = true;
  setInput(false);
  body.dataset.mood = "ominous";
  const line = "Leaving already? Go. I'll keep your reflection.";
  await Promise.all([typeWords(line), speak(line)]);
  await sleep(1200);
  goToSleep(false);
}

function setSleepText() {
  $("#sleeptext").textContent = cameraOn
    ? "the glass is cold. stand before it."
    : "the glass is cold. press enter to wake it.";
}

function renderHud() {
  const voiceState = voiceOk ? "voice on (f2)" : support.speak ? "voice out only" : "text only";
  $("#hud").textContent = `VESPER · ${mode} · ${voiceState}`.toUpperCase();
}

// ---------- input ----------

$("#talk").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  lastViaVoice = false;
  send(text);
});
mic.addEventListener("click", toggleListen);

document.addEventListener("keydown", (e) => {
  if (state === "veiled") {
    e.preventDefault();
    sound.unlock();
    sound.level(0.1);
    $("#veil").classList.add("gone");
    state = L.next(state, "unveil");
    setSleepText();
    loadWeather();
    return;
  }
  if (e.key === "F2") {
    e.preventDefault();
    toggleListen();
  } else if (state === "sleeping" && e.key === "Enter") {
    summon(true); // works even without a camera
  }
});
document.addEventListener("click", () => {
  if (state === "veiled") document.dispatchEvent(new KeyboardEvent("keydown", { key: " " }));
});

// ---------- weather plaque ----------

async function loadWeather() {
  try {
    const { weather } = await (await fetch("/api/weather")).json();
    $("#weather").textContent = L.weatherLine(weather);
  } catch {
    // Plaque stays blank; the ghost is told the weather is unknown.
  }
}
setInterval(loadWeather, 30 * 60 * 1000);

// ---------- local AI: who is at the mirror ----------

const reflection = $("#reflection");
reflection.addEventListener("error", () => reflection.classList.add("missing"));

async function poll() {
  try {
    const s = await (await fetch("/api/state")).json();
    mode = s.mode;
    const p = s.presence;
    if (p.enabled && !cameraOn) {
      reflection.classList.remove("missing");
      reflection.src = "/mirror.mjpg";
    }
    if (p.enabled !== cameraOn) {
      cameraOn = p.enabled;
      if (state === "sleeping") setSleepText();
    }
    present = p.present;
    $("#facemood").textContent = state === "awake" ? L.moodLabel(p.mood) : "";
    if (state === "awake" && present) seenSinceSummon = true;

    const now = Date.now();
    if (L.shouldSummon({ state, cameraOn, present, busy, now, cooldownUntil })) summon(false);
    else if (L.shouldDepart({ state, cameraOn, present, seenSinceSummon, busy })) depart();
    renderHud();
  } catch {
    // Server gone. Keep polling quietly.
  }
  setTimeout(poll, 600);
}
if (!cameraOn) reflection.classList.add("missing");
updateMic();
poll();

// Now and then the reflection is not quite yours.
(function glitch() {
  setTimeout(() => {
    if (state === "awake" && body.dataset.mood !== "care") {
      body.classList.add("glitch");
      setTimeout(() => body.classList.remove("glitch"), 120);
    }
    glitch();
  }, 9000 + Math.random() * 16000);
})();
