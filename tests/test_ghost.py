import json

import pytest

import ghost

WEATHER = {"city": "Norman", "now_f": 44, "high_f": 52, "low_f": 38, "rain_pct": 70,
           "wind_mph": 20, "sky": "light rain", "advice": ["heavy coat", "umbrella"]}


class FakeCloud:
    def __init__(self, replies=None, error=None):
        self.replies = list(replies or [])
        self.error = error
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.replies.pop(0)


class ExplodingCloud:
    def chat(self, messages):
        raise AssertionError("cloud must not be called")


# ---------- helpers ----------

@pytest.mark.parametrize("hour,expected", [(6, "morning"), (13, "afternoon"), (19, "evening"), (2, "night"), (23, "night")])
def test_time_of_day(hour, expected):
    assert ghost.time_of_day(hour) == expected


def test_context_includes_weather_mood_and_time():
    ctx = ghost.build_context(WEATHER, "tired", hour=8)
    assert "Norman" in ctx and "44" in ctx and "light rain" in ctx
    assert "heavy coat" in ctx and "umbrella" in ctx
    assert "tired" in ctx
    assert "morning" in ctx


def test_context_without_weather_or_mood():
    ctx = ghost.build_context(None, None, hour=15)
    assert "unknown" in ctx.lower()
    assert "afternoon" in ctx


@pytest.mark.parametrize("text", [
    "I want to kill myself", "thinking about suicide", "I don't want to live anymore",
    "i dont want to live", "I want to end my life", "I've been hurting myself", "I want to die",
    "having thoughts of self-harm",
])
def test_crisis_detected(text):
    assert ghost.is_crisis(text)


@pytest.mark.parametrize("text", ["I'm dying to see that movie", "this exam is killing me", "I'm fine", "my plants died"])
def test_crisis_not_triggered_by_figures_of_speech(text):
    assert not ghost.is_crisis(text)


def test_parse_reply_json():
    reply = ghost.parse_reply('{"say": "The glass is cold today.", "mood": "ominous"}')
    assert reply == {"say": "The glass is cold today.", "mood": "ominous", "bye": False}


def test_parse_reply_json_inside_chatter():
    reply = ghost.parse_reply('Here you go: {"say": "Wear a coat.", "mood": "worried", "bye": true} hope that helps')
    assert reply["say"] == "Wear a coat." and reply["mood"] == "worried" and reply["bye"] is True


def test_parse_reply_unknown_mood_becomes_calm():
    assert ghost.parse_reply('{"say": "hi", "mood": "giddy"}')["mood"] == "calm"


def test_parse_reply_plain_text():
    reply = ghost.parse_reply("Just words, no json")
    assert reply == {"say": "Just words, no json", "mood": "calm", "bye": False}


# ---------- ghost behaviour ----------

def test_crisis_bypasses_cloud_and_gives_988():
    g = ghost.Ghost(cloud=ExplodingCloud())
    reply = g.ask("honestly I want to end my life", ghost.build_context(None, None, 12))
    assert "988" in reply["say"]
    assert reply["mood"] == "care"
    assert reply["source"] == "safety"


def test_offline_greeting_mentions_weather_and_outfit():
    g = ghost.Ghost()
    reply = g.summon(ghost.build_context(WEATHER, None, 8), weather=WEATHER)
    assert reply["source"] == "offline"
    assert "44" in reply["say"]
    assert "coat" in reply["say"] or "umbrella" in reply["say"]
    assert "?" in reply["say"]  # always ends by asking how they are


def test_offline_greeting_comments_on_face_mood():
    reply = ghost.Ghost().summon("", weather=None, face_mood="tired")
    assert "tired" in reply["say"].lower() or "eyes" in reply["say"].lower()


def test_offline_greeting_without_weather():
    reply = ghost.Ghost().summon("", weather=None)
    assert reply["say"] and reply["mood"] in ghost.MOODS


def test_offline_sad_reply_is_worried_and_gives_a_suggestion():
    reply = ghost.Ghost().ask("I feel really sad and lonely today", "")
    assert reply["mood"] == "worried"
    assert any(w in reply["say"].lower() for w in ("water", "sleep", "walk", "call", "eat", "breathe", "friend"))


def test_offline_happy_reply_is_pleased():
    assert ghost.Ghost().ask("I'm great, feeling happy", "")["mood"] == "pleased"


def test_offline_goodbye():
    reply = ghost.Ghost().ask("goodbye", "")
    assert reply["bye"] is True


def test_cloud_reply_used_with_context_and_history():
    cloud = FakeCloud([
        json.dumps({"say": "Ah. You return.", "mood": "ominous"}),
        json.dumps({"say": "Rest, then.", "mood": "worried"}),
    ])
    g = ghost.Ghost(cloud=cloud)
    g.summon("CTX-1")
    reply = g.ask("I'm tired", "CTX-2")
    assert reply == {"say": "Rest, then.", "mood": "worried", "bye": False, "source": "cloud"}
    sent = cloud.calls[1]
    assert sent[0]["role"] == "system" and "VESPER" in sent[0]["content"]
    assert any("CTX-2" in m["content"] for m in sent if m["role"] == "system")
    assert not any("CTX-1" in m["content"] for m in sent if m["role"] == "system")  # only the fresh context
    assert {"role": "user", "content": "I'm tired"} in sent
    assert {"role": "assistant", "content": json.dumps({"say": "Ah. You return.", "mood": "ominous"})} in sent


def test_cloud_failure_falls_back_to_offline():
    g = ghost.Ghost(cloud=FakeCloud(error=OSError("no network")))
    reply = g.ask("I'm great", "")
    assert reply["source"] == "offline"
    assert reply["mood"] == "pleased"


def test_summon_resets_history():
    cloud = FakeCloud([json.dumps({"say": "a"}), json.dumps({"say": "b"}), json.dumps({"say": "c"})])
    g = ghost.Ghost(cloud=cloud)
    g.summon("")
    g.ask("hello", "")
    g.summon("")
    assert not any(m.get("content") == "hello" for m in cloud.calls[2])


def test_history_is_capped():
    cloud = FakeCloud([json.dumps({"say": str(i)}) for i in range(60)])
    g = ghost.Ghost(cloud=cloud)
    for i in range(30):
        g.ask(f"msg {i}", "")
    assert len(cloud.calls[-1]) <= ghost.MAX_HISTORY + 2  # system prompt + context + history


def test_mode_names():
    assert ghost.Ghost().mode == "offline"
    cloud = FakeCloud()
    cloud.name = "cloud:test-model"
    assert ghost.Ghost(cloud=cloud).mode == "cloud:test-model"
