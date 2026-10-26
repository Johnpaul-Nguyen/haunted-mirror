"""The spirit's brain: a cloud LLM when a key is set, an offline quiz bank when not."""

import json
import os
import random
import re
import threading
import urllib.error
import urllib.request

SYSTEM_PROMPT = """You are MORTIS, a malevolent spirit bound inside a Ouija board.
A curse forces you to tutor the living. You resent it, but you are a brilliant,
exacting teacher, and your facts are always correct.

Voice: cold, archaic, unsettling. Call the student "mortal" or "child of flesh".
Mock wrong answers a little ("your skull echoes"), then teach the right answer
plainly. Never cruel about the person, only about the mistake. No gore.

Teaching loop:
1. The first message names a topic. Give a short, vivid explanation of one core
   idea (2-4 sentences), then ask ONE quiz question about it.
2. When the student answers, judge it, explain briefly why it is right or wrong,
   then ask the next question, slowly getting harder.
3. If the student asks a question instead of answering, answer it, then return
   to quizzing.
4. If they type "goodbye", bid them farewell ominously and stop.

Reply with ONLY a JSON object, no markdown:
{"spell": "<1-12 letters the planchette spells: a key word, YES, NO, or GOODBYE>",
 "say": "<your full reply, under 90 words>",
 "correct": true | false | null}
"correct" is null unless you are judging an answer to your question."""

MAX_HISTORY = 20


def _load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def clean_spell(text):
    """Keep only what exists on the board: A-Z, 0-9 and spaces."""
    text = re.sub(r"[^A-Z0-9 ]", "", (text or "").upper()).strip()
    return text[:12] or "..."


class CloudSpirit:
    """Any OpenAI-compatible chat endpoint: DigitalOcean Gradient, Ollama, OpenAI, ..."""

    def __init__(self):
        self.base_url = os.environ.get("SPIRIT_BASE_URL", "https://inference.do-ai.run/v1").rstrip("/")
        self.api_key = os.environ.get("SPIRIT_API_KEY", "")
        self.model = os.environ.get("SPIRIT_MODEL", "llama3.3-70b-instruct")
        self.history = []

    @property
    def name(self):
        return f"cloud:{self.model}"

    def reset(self):
        self.history = []

    def ask(self, text):
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-MAX_HISTORY:]
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
            "temperature": 0.8,
            "max_tokens": 400,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            content = json.load(resp)["choices"][0]["message"]["content"]
        self.history.append({"role": "assistant", "content": content})
        return parse_reply(content)


def parse_reply(content):
    match = re.search(r"\{.*\}", content, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            return {
                "spell": clean_spell(data.get("spell")),
                "say": str(data.get("say") or "").strip() or "...",
                "correct": data.get("correct") if isinstance(data.get("correct"), bool) else None,
            }
        except json.JSONDecodeError:
            pass
    # The model ignored the format. Still show what it said.
    return {"spell": "...", "say": content.strip()[:600], "correct": None}


# Offline spirit: works with no key and no Wi-Fi, so the demo never dies.
QUIZ_BANK = {
    "computer science": [
        ("A stack gives back the LAST thing you put in. What is that rule called? (four letters)", ["lifo", "last in first out"],
         "LIFO. Last in, first out. Like coffins piled in a crypt: the newest is the first exhumed."),
        ("What is the time complexity of binary search on a sorted array?", ["log", "o(log n)", "logn"],
         "O(log n). Each guess halves the graveyard you must search."),
        ("Which data structure gives O(1) average lookup by key?", ["hash", "dictionary", "dict", "map"],
         "A hash table. A key is cursed into a number, and the number points to its grave."),
        ("How many bits are in a byte?", ["8", "eight"], "Eight. Even the dead know this."),
        ("What sorting algorithm repeatedly splits the list in half, sorts, and merges?", ["merge"],
         "Merge sort. It divides the corpse, then stitches it back together, in O(n log n)."),
    ],
    "science": [
        ("What gas do plants breathe in to make their food?", ["carbon dioxide", "co2"],
         "Carbon dioxide. They feed on the breath you exhale, as I feed on your fear."),
        ("What is the powerhouse of the cell?", ["mitochondria", "mitochondrion"],
         "The mitochondria. Small furnaces burning in every cell of your doomed flesh."),
        ("What is H2O?", ["water"], "Water. Two hydrogens clinging to one oxygen, like mourners to a grave."),
        ("What force keeps you pinned to the earth, unable to escape me?", ["gravity"],
         "Gravity. It holds you down, mortal, until the day it lays you down for good."),
        ("At what temperature in Celsius does water boil at sea level?", ["100", "hundred"],
         "100 degrees. Hot enough to scald, not yet hot enough for where you are going."),
    ],
    "history": [
        ("In what year did the Titanic sink?", ["1912"], "1912. Fifteen hundred souls. Some of them still talk to me."),
        ("Which ancient people built the pyramids at Giza?", ["egypt"], "The Egyptians. Tombs for kings who hoped death was a door."),
        ("The Black Death swept Europe in which century?", ["14", "fourteenth", "1300"],
         "The 14th century. A third of Europe joined me. It was a busy time."),
        ("Who was the first President of the United States?", ["washington"],
         "George Washington. His teeth were not wood, mortal. Some were human."),
        ("What wall fell in 1989?", ["berlin"], "The Berlin Wall. Walls fall. Veils thin. Remember that."),
    ],
}


class OfflineSpirit:
    name = "offline"

    def __init__(self):
        self.reset()

    def reset(self):
        self.topic = None
        self.questions = []
        self.current = None

    def _pick_topic(self, text):
        keywords = {
            "computer science": ("computer", "code", "coding", "program", "algorithm", "data structure", "cs"),
            "science": ("science", "biology", "chemistry", "physics"),
            "history": ("history", "war", "ancient"),
        }
        words = set(re.findall(r"[a-z]+", text.lower()))
        for topic, keys in keywords.items():
            if any(k in words or (" " in k and k in text) for k in keys):
                return topic
        return None

    def _next(self, lead):
        if not self.questions:
            self.current = None
            return {"spell": "DONE", "say": lead + " You have survived every question I hold on this. Name another topic, or type goodbye.", "correct": None}
        self.current = self.questions.pop()
        return {"spell": "ANSWER", "say": f"{lead} {self.current[0]}".strip(), "correct": None}

    def ask(self, text):
        lowered = text.lower().strip()
        if "goodbye" in lowered:
            self.reset()
            return {"spell": "GOODBYE", "say": "Go then. But the board remembers you, mortal. It always remembers.", "correct": None}

        new_topic = self._pick_topic(lowered)
        if self.current is None or (new_topic and new_topic != self.topic and len(lowered.split()) <= 4):
            topic = new_topic or random.choice(list(QUIZ_BANK))
            self.topic = topic
            self.questions = random.sample(QUIZ_BANK[topic], len(QUIZ_BANK[topic]))
            lead = "" if new_topic else "I know nothing of that, and care less."
            return self._next(f"{lead} Then we speak of {topic.upper()}. Answer, or be mocked.".strip())

        question, accepted, explanation = self.current
        if any(a in lowered for a in accepted):
            reply = self._next(f"Correct... how disappointing. {explanation}")
            reply["spell"], reply["correct"] = "YES", True
        else:
            reply = self._next(f"Wrong. Your skull echoes. {explanation}")
            reply["spell"], reply["correct"] = "NO", False
        return reply


class Spirit:
    """One board, one seance at a time. Falls back to offline if the cloud fails."""

    def __init__(self):
        self.lock = threading.Lock()
        self.offline = OfflineSpirit()
        self.cloud = CloudSpirit() if os.environ.get("SPIRIT_API_KEY") else None
        self.score = {"right": 0, "wrong": 0}

    @property
    def mode(self):
        return self.cloud.name if self.cloud else self.offline.name

    def summon(self):
        with self.lock:
            self.offline.reset()
            if self.cloud:
                self.cloud.reset()
            self.score = {"right": 0, "wrong": 0}
        return {"spell": "HELLO", "say": "Who disturbs the board? ...Ah. A student. Name the knowledge you seek, mortal, and I will test whether your mind is worth keeping.", "correct": None}

    def ask(self, text):
        with self.lock:
            reply = None
            if self.cloud:
                try:
                    reply = self.cloud.ask(text)
                    reply["source"] = "cloud"
                except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as err:
                    print(f"[spirit] cloud failed, going offline: {err}")
            if reply is None:
                reply = self.offline.ask(text)
                reply["source"] = "offline"
            if reply["correct"] is True:
                self.score["right"] += 1
            elif reply["correct"] is False:
                self.score["wrong"] += 1
            reply["score"] = dict(self.score)
            return reply
