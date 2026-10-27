"""VESPER, the ghost in the mirror: a cloud LLM when a key is set, scripted when not."""

import json
import os
import re
import threading
import urllib.request

MOODS = {"calm", "pleased", "worried", "ominous", "care"}
MAX_HISTORY = 16

SYSTEM_PROMPT = """You are VESPER, a ghost trapped behind a bathroom mirror for a hundred years.
Each day a living person stands in front of you. You are eerie, dry and a little
menacing, but secretly you care about them: they are the only company you have.

Your job is a short daily check-in, spoken aloud:
1. When they appear, greet them by time of day, mention what you see in their face
   if the context gives a mood guess, tell them the weather and what to wear in a
   creepy way, then ask how they really are.
2. Listen. Reflect back what they said. If they seem low, stressed or tired, give ONE
   small, concrete suggestion (water, food, sleep, a walk, a breath, message a friend).
3. Never diagnose, never lecture. You are company, not a therapist.
4. If they say goodbye, let them go ominously and set "bye" to true.

Keep every reply under 55 words: it is read aloud. No emoji, no markdown.
Reply with ONLY a JSON object:
{"say": "<what you say>", "mood": "calm" | "pleased" | "worried" | "ominous", "bye": false}"""

CRISIS_PATTERNS = [
    r"\bkill(ing)? myself\b", r"\bsuicid", r"\bend(ing)? (my life|it all)\b",
    r"\b(want|wanna|going|ready) to die\b", r"\bself[- ]?harm", r"\bhurt(ing)? myself\b",
    r"\bdon'?t want to (live|be alive|exist)\b", r"\bno reason to live\b", r"\bbetter off dead\b",
]

CRISIS_REPLY = (
    "I'm stepping out of the mirror for a moment, because this matters more than any haunting. "
    "I'm really glad you told me. Please talk to a real person right now: in the US, call or text 988, "
    "the Suicide and Crisis Lifeline, any time. Elsewhere, call your local emergency number. "
    "Is there someone you trust you can reach out to tonight?"
)


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
if hasattr(__import__("time"), "tzset"):
    __import__("time").tzset()  # apply TZ from .env (boards often default to UTC)


def is_crisis(text):
    text = text.lower().replace("’", "'")
    return any(re.search(p, text) for p in CRISIS_PATTERNS)


def time_of_day(hour):
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def build_context(weather, face_mood, hour):
    """The facts the ghost may use this turn, given to the model as a system message."""
    lines = [f"Time of day: {time_of_day(hour)}."]
    if weather:
        lines.append(
            f"Weather in {weather['city']}: {weather['now_f']}F now, {weather['sky']}, high {weather['high_f']}F, "
            f"low {weather['low_f']}F, {weather['rain_pct']}% chance of rain, wind {weather['wind_mph']} mph. "
            f"Suggested clothing: {', '.join(weather['advice'])}."
        )
    else:
        lines.append("Weather: unknown (do not invent it).")
    lines.append(f"Their face looks: {face_mood}." if face_mood else "Their face: unknown.")
    return " ".join(lines)


def parse_reply(content):
    match = re.search(r"\{.*\}", content, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            mood = data.get("mood")
            return {
                "say": str(data.get("say") or "").strip() or "...",
                "mood": mood if mood in MOODS else "calm",
                "bye": data.get("bye") is True,
            }
        except json.JSONDecodeError:
            pass
    return {"say": content.strip()[:500] or "...", "mood": "calm", "bye": False}


class CloudClient:
    """Any OpenAI-compatible chat endpoint: DigitalOcean Gradient, Ollama, OpenAI, ..."""

    def __init__(self):
        self.base_url = os.environ.get("SPIRIT_BASE_URL", "https://inference.do-ai.run/v1").rstrip("/")
        self.api_key = os.environ.get("SPIRIT_API_KEY", "")
        self.model = os.environ.get("SPIRIT_MODEL", "deepseek-v4.1-flash")
        self.name = f"cloud:{self.model}"

    def chat(self, messages):
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0.8, "max_tokens": 300}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["choices"][0]["message"]["content"]


# ---------- offline ghost: scripted, so the mirror works with no key or Wi-Fi ----------

GREETINGS = {
    "morning": "Morning light finds you again, mortal. Pity.",
    "afternoon": "Afternoon. You've wasted half the day. I've wasted a century.",
    "evening": "Evening. The glass gets colder now. So do I.",
    "night": "It's late. This is my hour, not yours.",
}
FACE_LINES = {
    "smiling": "You're smiling. I find that... suspicious.",
    "tired": "Those eyes are heavy. The dead sleep better than you do.",
}
SAD_WORDS = {"sad", "lonely", "alone", "tired", "exhausted", "stressed", "anxious", "bad", "awful", "terrible",
             "depressed", "down", "angry", "upset", "sick", "overwhelmed", "worried", "scared", "cry", "crying", "rough"}
HAPPY_WORDS = {"good", "great", "happy", "awesome", "amazing", "excited", "wonderful", "fantastic", "better", "glad"}
BYE_PATTERN = r"\b(goodbye|bye|good night|goodnight|see you)\b"

SAD_REPLIES = [
    "Mm. I know lonely. I've had this mirror to myself for a century. Drink a glass of water, then message one living friend. Will you?",
    "Even ghosts get tired. Sleep before midnight tonight. That hour belongs to me anyway. What weighs on you most?",
    "Breathe in for four, hold for four, out for four. Yes, I'm watching. Better? Tell me what happened.",
    "Go outside and walk for ten minutes. The sun can't hurt you, unlike me. What would make today one notch better?",
    "Have you eaten? Bodies are such fragile things. Eat something, then come tell me more.",
]
HAPPY_REPLIES = [
    "Good. Joy looks strange on the living, but it suits you. What went right?",
    "How unsettling. A happy one. Hold on to it. Tell me why.",
    "Delightful. I'll feed on that for days. What's next for you today?",
]
NEUTRAL_REPLIES = [
    "Go on. I have all of eternity, and you have... less. Tell me more.",
    "Hm. And what are you not telling me?",
    "I'm listening. I'm always listening. What's on your mind today?",
]


def _words(text):
    return set(re.findall(r"[a-z']+", text.lower()))


class OfflineGhost:
    def __init__(self):
        self.turn = 0

    def _pick(self, options):
        self.turn += 1
        return options[self.turn % len(options)]

    def greet(self, hour, weather, face_mood):
        parts = [GREETINGS[time_of_day(hour)]]
        if face_mood in FACE_LINES:
            parts.append(FACE_LINES[face_mood])
        if weather:
            parts.append(f"Outside in {weather['city']} it's {weather['now_f']} degrees and {weather['sky']}, "
                         f"with a high of {weather['high_f']}.")
            parts.append(f"Dress for it: {', '.join(weather['advice'])}. I'd hate for anything to... happen to you.")
        parts.append("Now. How are you, really?")
        mood = "worried" if face_mood == "tired" else "ominous"
        return {"say": " ".join(parts), "mood": mood, "bye": False}

    def reply(self, text):
        lowered = text.lower()
        if re.search(BYE_PATTERN, lowered):
            return {"say": "Leave, then. I'll be right here, behind your reflection. I always am.", "mood": "ominous", "bye": True}
        words = _words(text)
        negated_happy = re.search(r"\bnot (so |very |that |too )?(good|great|happy|okay|ok|fine)\b", lowered)
        if negated_happy or words & SAD_WORDS:
            return {"say": self._pick(SAD_REPLIES), "mood": "worried", "bye": False}
        if words & HAPPY_WORDS:
            return {"say": self._pick(HAPPY_REPLIES), "mood": "pleased", "bye": False}
        return {"say": self._pick(NEUTRAL_REPLIES), "mood": "calm", "bye": False}


class Ghost:
    """One mirror, one visitor at a time. Falls back to offline if the cloud fails."""

    def __init__(self, cloud=None):
        self.cloud = cloud
        self.offline = OfflineGhost()
        self.history = []
        self.lock = threading.Lock()

    @property
    def mode(self):
        return getattr(self.cloud, "name", "cloud") if self.cloud else "offline"

    def _cloud_turn(self, user_text, context):
        if not self.cloud:
            return None
        history = (self.history + [{"role": "user", "content": user_text}])[-MAX_HISTORY:]
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"Context right now: {context}"}] + history
        try:
            content = self.cloud.chat(messages)
        except (OSError, KeyError, IndexError, ValueError) as err:
            print(f"[ghost] cloud failed, going offline: {err}")
            return None
        if not (content or "").strip():
            print("[ghost] cloud returned no text, going offline")
            return None
        self.history = (history + [{"role": "assistant", "content": content}])[-MAX_HISTORY:]
        reply = parse_reply(content)
        reply["source"] = "cloud"
        return reply

    def summon(self, context, weather=None, face_mood=None, hour=None):
        if hour is None:
            import time
            hour = time.localtime().tm_hour
        with self.lock:
            self.history = []
            reply = self._cloud_turn("[A living person steps in front of the mirror.]", context)
            if reply is None:
                reply = self.offline.greet(hour, weather, face_mood)
                reply["source"] = "offline"
            return reply

    def ask(self, text, context):
        with self.lock:
            if is_crisis(text):
                return {"say": CRISIS_REPLY, "mood": "care", "bye": False, "source": "safety"}
            reply = self._cloud_turn(text, context)
            if reply is None:
                reply = self.offline.reply(text)
                reply["source"] = "offline"
            return reply
