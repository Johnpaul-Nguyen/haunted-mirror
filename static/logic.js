// Pure logic for the mirror, kept apart from the DOM so Node can test it.
(function (root) {
  const EERIE_VOICE = /zira|samantha|serena|victoria|karen|moira|tessa|hazel|susan|female/i;

  function cleanForSpeech(text) {
    return String(text || "")
      .replace(/[*_`#~]/g, "")
      .replace(/\p{Extended_Pictographic}/gu, "")
      .replace(/\b988\b/g, "nine eight eight")
      .replace(/\s+/g, " ")
      .trim();
  }

  function pickVoice(voices) {
    if (!voices || !voices.length) return null;
    const english = voices.filter((v) => /^en/i.test(v.lang));
    return english.find((v) => EERIE_VOICE.test(v.name)) || english[0] || voices[0];
  }

  const TRANSITIONS = {
    veiled: { unveil: "sleeping" },
    sleeping: { face: "summoning", manual: "summoning" },
    summoning: { summoned: "awake" },
    awake: { left: "departing", bye: "departing" },
    departing: { slept: "sleeping" },
  };

  function next(state, event) {
    return (TRANSITIONS[state] && TRANSITIONS[state][event]) || state;
  }

  function shouldSummon({ state, cameraOn, present, busy, now, cooldownUntil }) {
    return state === "sleeping" && cameraOn && present && !busy && now > cooldownUntil;
  }

  // A manual (Enter) summon must not end just because the camera sees nobody.
  function shouldDepart({ state, cameraOn, present, seenSinceSummon, busy }) {
    return state === "awake" && cameraOn && !present && seenSinceSummon && !busy;
  }

  function weatherLine(w) {
    if (!w) return "";
    return `${w.city} · ${w.now_f}° · ${w.sky} · rain ${w.rain_pct}%`.toUpperCase();
  }

  function moodLabel(mood) {
    return mood ? `THE GLASS SEES: ${mood.toUpperCase()}` : "";
  }

  function speechSupport(win) {
    return {
      listen: Boolean(win.SpeechRecognition || win.webkitSpeechRecognition),
      speak: Boolean(win.speechSynthesis),
    };
  }

  function voiceError(code) {
    if (code === "no-speech" || code === "aborted") return "";
    if (code === "not-allowed" || code === "service-not-allowed") return "The mirror can't hear you: allow the microphone, or type instead.";
    if (code === "network") return "Voice needs the internet in this browser. Type instead.";
    if (code === "audio-capture") return "No microphone found. Type instead.";
    return "Voice failed. Type instead.";
  }

  // speechSynthesis 'end' events are unreliable on some Linux builds; never wait forever.
  function speakTimeout(text) {
    const words = String(text || "").split(/\s+/).filter(Boolean).length;
    return Math.max(3000, words * 520);
  }

  const api = { cleanForSpeech, pickVoice, next, shouldSummon, shouldDepart, weatherLine, moodLabel, speechSupport, voiceError, speakTimeout };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MirrorLogic = api;
})(this);
