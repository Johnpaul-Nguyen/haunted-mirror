const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/logic.js");

test("cleanForSpeech strips markdown, emoji and spaces", () => {
  assert.equal(L.cleanForSpeech("**Hello**   there _mortal_ 👻"), "Hello there mortal");
});

test("cleanForSpeech reads 988 as digits", () => {
  assert.match(L.cleanForSpeech("call or text 988 now"), /nine eight eight/);
});

test("cleanForSpeech handles empty input", () => {
  assert.equal(L.cleanForSpeech(""), "");
  assert.equal(L.cleanForSpeech(undefined), "");
});

test("pickVoice prefers an eerie English female voice", () => {
  const voices = [
    { name: "Microsoft David", lang: "en-US" },
    { name: "Microsoft Zira", lang: "en-US" },
    { name: "Hans", lang: "de-DE" },
  ];
  assert.equal(L.pickVoice(voices).name, "Microsoft Zira");
});

test("pickVoice falls back to any English voice, then anything, then null", () => {
  assert.equal(L.pickVoice([{ name: "x", lang: "de-DE" }, { name: "y", lang: "en-GB" }]).name, "y");
  assert.equal(L.pickVoice([{ name: "x", lang: "de-DE" }]).name, "x");
  assert.equal(L.pickVoice([]), null);
});

test("state machine: full visit", () => {
  let s = "veiled";
  s = L.next(s, "unveil"); assert.equal(s, "sleeping");
  s = L.next(s, "face"); assert.equal(s, "summoning");
  s = L.next(s, "summoned"); assert.equal(s, "awake");
  s = L.next(s, "left"); assert.equal(s, "departing");
  s = L.next(s, "slept"); assert.equal(s, "sleeping");
});

test("state machine: manual summon and goodbye", () => {
  assert.equal(L.next("sleeping", "manual"), "summoning");
  assert.equal(L.next("awake", "bye"), "departing");
});

test("state machine ignores events that don't apply", () => {
  assert.equal(L.next("veiled", "face"), "veiled");
  assert.equal(L.next("awake", "face"), "awake");
  assert.equal(L.next("summoning", "left"), "summoning");
  assert.equal(L.next("sleeping", "left"), "sleeping");
});

test("shouldSummon respects the camera, presence and cooldown", () => {
  assert.equal(L.shouldSummon({ state: "sleeping", cameraOn: true, present: true, busy: false, now: 10, cooldownUntil: 0 }), true);
  assert.equal(L.shouldSummon({ state: "sleeping", cameraOn: true, present: true, busy: false, now: 10, cooldownUntil: 20 }), false);
  assert.equal(L.shouldSummon({ state: "sleeping", cameraOn: true, present: false, busy: false, now: 10, cooldownUntil: 0 }), false);
  assert.equal(L.shouldSummon({ state: "awake", cameraOn: true, present: true, busy: false, now: 10, cooldownUntil: 0 }), false);
  assert.equal(L.shouldSummon({ state: "sleeping", cameraOn: false, present: true, busy: false, now: 10, cooldownUntil: 0 }), false);
});

test("shouldDepart only after a face was seen, and never mid-reply", () => {
  const base = { state: "awake", cameraOn: true, present: false, seenSinceSummon: true, busy: false };
  assert.equal(L.shouldDepart(base), true);
  assert.equal(L.shouldDepart({ ...base, seenSinceSummon: false }), false); // manual summon, nobody seen yet
  assert.equal(L.shouldDepart({ ...base, busy: true }), false);
  assert.equal(L.shouldDepart({ ...base, present: true }), false);
  assert.equal(L.shouldDepart({ ...base, cameraOn: false }), false);
});

test("weatherLine formats the plaque", () => {
  const w = { city: "Norman", now_f: 44, sky: "light rain", rain_pct: 70 };
  assert.equal(L.weatherLine(w), "NORMAN · 44° · LIGHT RAIN · RAIN 70%");
  assert.equal(L.weatherLine(null), "");
});

test("moodLabel", () => {
  assert.equal(L.moodLabel("tired"), "THE GLASS SEES: TIRED");
  assert.equal(L.moodLabel(null), "");
});

test("speechSupport detects what the browser offers", () => {
  assert.deepEqual(L.speechSupport({}), { listen: false, speak: false });
  assert.deepEqual(L.speechSupport({ webkitSpeechRecognition: function () {}, speechSynthesis: {} }), { listen: true, speak: true });
});

test("voiceError turns recognition errors into plain advice", () => {
  assert.match(L.voiceError("not-allowed"), /microphone/i);
  assert.match(L.voiceError("network"), /internet/i);
  assert.equal(L.voiceError("no-speech"), "");
  assert.equal(L.voiceError("aborted"), "");
  assert.match(L.voiceError("something-new"), /type/i);
});

test("speakTimeout grows with text length and has a floor", () => {
  assert.equal(L.speakTimeout(""), 3000);
  assert.ok(L.speakTimeout("word ".repeat(50)) > L.speakTimeout("word ".repeat(5)));
});
