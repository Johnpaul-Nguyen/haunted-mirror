// Spirit Board front end: draws the board, moves the planchette, talks to the server.

const $ = (s) => document.querySelector(s);
const board = $("#board");
const planchette = $("#planchette");
const whisper = $("#whisper");
const asked = $("#asked");
const input = $("#q");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const REST = { x: 500, y: 412 };
const marks = {};

// ---------- board layout ----------

function addGlyph(key, text, x, y, cls, rot = 0) {
  const el = document.createElement("span");
  el.className = `glyph ${cls}`;
  el.textContent = text;
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  el.style.transform = `translate(-50%, -50%) rotate(${rot}deg)`;
  board.appendChild(el);
  marks[key] = { x, y, el };
}

function arc(chars, cx, cy, r, a0, a1) {
  [...chars].forEach((c, i) => {
    const deg = a0 + ((a1 - a0) * i) / (chars.length - 1);
    const a = (deg * Math.PI) / 180;
    addGlyph(c, c, cx + r * Math.cos(a), cy - r * Math.sin(a), "big", 90 - deg);
  });
}

arc("ABCDEFGHIJKLM", 500, 640, 440, 156, 24);
arc("NOPQRSTUVWXYZ", 500, 640, 335, 151, 29);
[..."1234567890"].forEach((c, i) => addGlyph(c, c, 302 + i * 44, 515, "digit"));
addGlyph("YES", "YES", 140, 95, "word");
addGlyph("NO", "NO", 860, 95, "word");
addGlyph("GOODBYE", "GOODBYE", 500, 592, "word");

function fit() {
  const s = Math.min((innerWidth - 32) / 1000, (innerHeight * 0.66) / 640, 1.4);
  document.documentElement.style.setProperty("--s", s.toFixed(3));
}
addEventListener("resize", fit);
fit();

// ---------- planchette ----------

function move(x, y, seconds = 0.5) {
  const tilt = (x - 500) / 40 + (Math.random() * 6 - 3);
  planchette.style.setProperty("--d", `${seconds}s`);
  // The lens centre sits at (65, 90) inside the planchette.
  planchette.style.transform = `translate(${x - 65}px, ${y - 90}px) rotate(${tilt}deg)`;
}
move(REST.x, REST.y, 0);

let driftTimer = null;
function startDrift() {
  stopDrift();
  const step = () => {
    const a = Math.random() * Math.PI * 2;
    move(REST.x + Math.cos(a) * 190, REST.y - 60 + Math.sin(a) * 70, 1.3);
  };
  step();
  driftTimer = setInterval(step, 1300);
}
function stopDrift() {
  clearInterval(driftTimer);
  driftTimer = null;
}

async function touch(mark) {
  move(mark.x, mark.y, 0.45);
  await sleep(480);
  mark.el.classList.add("lit");
  sound.tick();
  await sleep(300);
  mark.el.classList.remove("lit");
}

async function spell(word) {
  if (marks[word] && word.length > 1) {
    await touch(marks[word]);
    await sleep(500);
  } else {
    for (const c of word) {
      if (marks[c]) await touch(marks[c]);
      else { move(REST.x, REST.y, 0.4); await sleep(450); }
    }
  }
  move(REST.x, REST.y, 0.8);
}

async function typeWhisper(text, cls = "") {
  whisper.className = cls;
  const noise = "#%&@$?!/\\";
  for (let i = 1; i <= text.length; i++) {
    const tail = i < text.length ? noise[(Math.random() * noise.length) | 0] : "";
    whisper.textContent = text.slice(0, i) + tail;
    await sleep(text[i - 1] === "." ? 160 : 22);
  }
}

// ---------- sound (all synthesised, no files) ----------

const sound = (() => {
  let ctx, master, drone;

  function noise(seconds, brown) {
    const buf = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < d.length; i++) {
      const w = Math.random() * 2 - 1;
      if (brown) { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; } else d[i] = w;
    }
    return buf;
  }

  return {
    unlock() {
      if (ctx) return;
      ctx = new AudioContext();
      master = ctx.createGain();
      master.gain.value = 0.9;
      master.connect(ctx.destination);

      drone = ctx.createGain();
      drone.gain.value = 0;
      const lp = ctx.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 170;
      lp.connect(drone).connect(master);
      for (const f of [55, 55.7, 82.2]) {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = "sawtooth";
        o.frequency.value = f;
        g.gain.value = 0.22;
        o.connect(g).connect(lp);
        o.start();
      }
      const wind = ctx.createBufferSource();
      wind.buffer = noise(4, true);
      wind.loop = true;
      wind.connect(lp);
      wind.start();
      const lfo = ctx.createOscillator();
      const depth = ctx.createGain();
      lfo.frequency.value = 0.07;
      depth.gain.value = 90;
      lfo.connect(depth).connect(lp.frequency);
      lfo.start();
    },
    level(v) {
      if (ctx) drone.gain.setTargetAtTime(v, ctx.currentTime, 1.2);
    },
    tick() {
      if (!ctx) return;
      const src = ctx.createBufferSource();
      const hp = ctx.createBiquadFilter();
      const g = ctx.createGain();
      src.buffer = noise(0.05);
      hp.type = "highpass";
      hp.frequency.value = 1800;
      g.gain.setValueAtTime(0.35, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
      src.connect(hp).connect(g).connect(master);
      src.start();
    },
    screech() {
      if (!ctx) return;
      const t = ctx.currentTime;
      const g = ctx.createGain();
      const shaper = ctx.createWaveShaper();
      const curve = new Float32Array(256).map((_, i) => Math.tanh(((i - 128) / 128) * 6));
      shaper.curve = curve;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.5, t + 0.04);
      g.gain.exponentialRampToValueAtTime(0.001, t + 1.1);
      shaper.connect(g).connect(master);
      for (const detune of [0, 37]) {
        const o = ctx.createOscillator();
        o.type = "sawtooth";
        o.frequency.setValueAtTime(220 + detune, t);
        o.frequency.exponentialRampToValueAtTime(2600 + detune * 10, t + 0.5);
        o.frequency.exponentialRampToValueAtTime(900, t + 1.1);
        o.connect(shaper);
        o.start(t);
        o.stop(t + 1.2);
      }
      const hiss = ctx.createBufferSource();
      hiss.buffer = noise(1.1);
      hiss.connect(g);
      hiss.start(t);
    },
  };
})();

// ---------- the seance ----------

let state = "veiled"; // veiled -> sleeping -> awake
let busy = false;
let cooldownUntil = 0;
let cameraOn = false;
let seenSinceSummon = false; // a manual Enter summon stays until a face arrives and then leaves

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(res.status);
  return res.json();
}

async function scare() {
  sound.screech();
  $("#scare").classList.add("on");
  document.body.classList.add("shake");
  await sleep(1100);
  $("#scare").classList.remove("on");
  document.body.classList.remove("shake");
}

async function respond(reply) {
  busy = true;
  input.disabled = true;
  stopDrift();
  await spell(reply.spell || "...");
  const mood = reply.correct === true ? "right" : reply.correct === false ? "wrong" : "";
  await typeWhisper(reply.say || "...", mood);
  if (reply.score) showScore(reply.score);
  busy = false;
  if (reply.spell === "GOODBYE") {
    await sleep(3000);
    goToSleep(true);
    return;
  }
  input.disabled = false;
  input.focus();
}

async function summon() {
  if (state !== "sleeping" || busy) return;
  busy = true;
  state = "awake";
  seenSinceSummon = false;
  document.body.classList.remove("asleep");
  whisper.textContent = "";
  asked.textContent = "";
  showScore({ right: 0, wrong: 0 });
  await scare();
  sound.level(0.32);
  let reply;
  try {
    reply = await post("/api/summon");
  } catch {
    reply = { spell: "...", say: "The veil will not part. Is the server running?" };
  }
  busy = false;
  await respond(reply);
}

function goToSleep(afterGoodbye) {
  state = "sleeping";
  busy = false;
  stopDrift();
  move(REST.x, REST.y, 1.5);
  document.body.classList.add("asleep");
  input.disabled = true;
  input.value = "";
  sound.level(0.12);
  if (afterGoodbye) cooldownUntil = Date.now() + 15000;
  setSleepText();
}

async function depart() {
  busy = true;
  input.disabled = true;
  await typeWhisper("You flee? They always flee. I will be here when you return, mortal.", "wrong");
  await sleep(2500);
  goToSleep(false);
}

$("#ask").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || busy || state !== "awake") return;
  input.value = "";
  asked.textContent = `you asked: ${text}`;
  whisper.textContent = "";
  busy = true;
  input.disabled = true;
  startDrift();
  let reply;
  try {
    reply = await post("/api/ask", { text });
  } catch {
    reply = { spell: "...", say: "The veil grows thick. The spirit cannot hear you. (server unreachable)" };
  }
  busy = false;
  await respond(reply);
});

document.addEventListener("keydown", (e) => {
  if (state === "veiled") {
    sound.unlock();
    sound.level(0.12);
    $("#veil").classList.add("gone");
    state = "sleeping";
    setSleepText();
    e.preventDefault();
    return;
  }
  // Enter always works as a manual summon, in case the camera is missing or shy.
  if (state === "sleeping" && e.key === "Enter") summon();
});
document.addEventListener("click", () => {
  if (state === "veiled") document.dispatchEvent(new KeyboardEvent("keydown", { key: " " }));
});

function setSleepText() {
  $("#sleeptext").textContent = cameraOn
    ? "the board is cold. sit before the glass to summon it."
    : "the board is cold. press enter to summon it.";
}

function showScore(score) {
  hudScore = `right ${score.right} · wrong ${score.wrong}`;
  renderHud();
}

let hudMode = "";
let hudScore = "";
function renderHud() {
  $("#hud").textContent = [`MORTIS · ${hudMode}`, hudScore].filter(Boolean).join(" · ").toUpperCase();
}

// ---------- local AI: presence from the camera ----------

async function poll() {
  try {
    const s = await (await fetch("/api/state")).json();
    hudMode = s.mode;
    renderHud();
    const p = s.presence;
    if (p.enabled !== cameraOn) {
      cameraOn = p.enabled;
      $("#scry").hidden = !cameraOn;
      if (state === "sleeping") setSleepText();
    }
    if (cameraOn) {
      $("#scryimg").src = `/api/scry.jpg?t=${Date.now()}`;
      $("#scry").classList.toggle("seen", p.faces > 0);
      $("#scrylabel").textContent = p.faces > 0 ? "IT SEES YOU" : "IT SEES NO ONE";
      if (p.present && state === "sleeping" && !busy && Date.now() > cooldownUntil) summon();
      if (p.present && state === "awake") seenSinceSummon = true;
      if (!p.present && state === "awake" && seenSinceSummon && !busy) depart();
    }
  } catch {
    // Server gone. Keep polling quietly.
  }
  setTimeout(poll, 600);
}
poll();

// Every so often the board twitches.
(function twitch() {
  setTimeout(() => {
    if (state === "awake") {
      document.body.classList.add("glitch");
      setTimeout(() => document.body.classList.remove("glitch"), 230);
    }
    twitch();
  }, 7000 + Math.random() * 14000);
})();
