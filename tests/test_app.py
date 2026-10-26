import http.client
import json
import threading

import pytest

import app
from ghost import Ghost

WEATHER = {"city": "Norman", "now_f": 44, "high_f": 52, "low_f": 38, "rain_pct": 70,
           "wind_mph": 20, "sky": "light rain", "advice": ["heavy coat", "umbrella"]}
JPEG = b"\xff\xd8fakejpeg\xff\xd9"


class FakePresence:
    def __init__(self, mood=None):
        self.mood = mood
        self.calls = 0

    def state(self):
        return {"enabled": True, "present": True, "faces": 1, "mood": self.mood, "error": None}

    def frame(self):
        self.calls += 1
        return self.calls, JPEG


class FakeWeather:
    def __init__(self, report):
        self.report = report

    def get(self):
        return self.report


@pytest.fixture
def server():
    def start(weather=WEATHER, mood="tired"):
        srv = app.make_server(0, Ghost(), FakePresence(mood), FakeWeather(weather))
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        servers.append(srv)
        return srv.server_address[1]

    servers = []
    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def request(port, method, path, body=None, raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    conn.request(method, path, body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, resp.getheader("Content-Type"), data


def test_index_served(server):
    status, ctype, body = request(server(), "GET", "/")
    assert status == 200 and "text/html" in ctype
    assert b"<title>Haunted Mirror</title>" in body


def test_static_js_served(server):
    status, ctype, _ = request(server(), "GET", "/mirror.js")
    assert status == 200 and "javascript" in ctype


@pytest.mark.parametrize("path", ["/../app.py", "/..%2Fapp.py", "/nope.txt"])
def test_no_escape_from_static(server, path):
    status, _, _ = request(server(), "GET", path)
    assert status == 404


def test_state(server):
    status, _, body = request(server(), "GET", "/api/state")
    data = json.loads(body)
    assert status == 200
    assert data["mode"] == "offline"
    assert data["presence"]["mood"] == "tired"


def test_weather(server):
    _, _, body = request(server(), "GET", "/api/weather")
    assert json.loads(body)["weather"]["city"] == "Norman"


def test_weather_missing(server):
    _, _, body = request(server(weather=None), "GET", "/api/weather")
    assert json.loads(body) == {"weather": None}


def test_summon_uses_weather_and_face_mood(server):
    status, _, body = request(server(), "POST", "/api/summon", {})
    reply = json.loads(body)
    assert status == 200
    assert "44" in reply["say"]
    assert "eyes" in reply["say"].lower()


def test_say(server):
    status, _, body = request(server(), "POST", "/api/say", {"text": "I'm feeling great"})
    assert status == 200
    assert json.loads(body)["mood"] == "pleased"


def test_say_crisis(server):
    _, _, body = request(server(), "POST", "/api/say", {"text": "I want to kill myself"})
    assert "988" in json.loads(body)["say"]


def test_say_empty_is_400(server):
    status, _, _ = request(server(), "POST", "/api/say", {"text": "   "})
    assert status == 400


def test_bad_json_is_400(server):
    status, _, _ = request(server(), "POST", "/api/say", raw=b"{not json")
    assert status == 400


def test_unknown_post_is_404(server):
    status, _, _ = request(server(), "POST", "/api/nothing", {})
    assert status == 404


def test_mirror_stream_sends_jpeg_parts(server):
    conn = http.client.HTTPConnection("127.0.0.1", server(), timeout=5)
    conn.request("GET", "/mirror.mjpg")
    resp = conn.getresponse()
    assert resp.status == 200
    assert resp.getheader("Content-Type").startswith("multipart/x-mixed-replace")
    chunk = resp.read(200)
    conn.close()
    assert b"--frame" in chunk and b"image/jpeg" in chunk and JPEG in chunk
