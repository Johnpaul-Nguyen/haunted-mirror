"""Haunted Mirror: a ghost that checks on you each day. Run `python app.py`, open http://localhost:8666"""

import json
import mimetypes
import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ghost import CloudClient, Ghost, build_context

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.realpath(os.path.join(ROOT, "static"))
mimetypes.add_type("text/javascript", ".js")


def make_server(port, ghost, presence, weather):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if "/api/state" not in self.path:
                super().log_message(fmt, *args)

        def _send(self, code, body, content_type="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _context(self):
            face_mood = presence.state().get("mood")
            report = weather.get()
            return report, face_mood, build_context(report, face_mood, time.localtime().tm_hour)

        def do_GET(self):
            path = urllib.parse.unquote(self.path.split("?")[0])
            if path == "/api/state":
                return self._send(200, {"presence": presence.state(), "mode": ghost.mode})
            if path == "/api/weather":
                return self._send(200, {"weather": weather.get()})
            if path == "/mirror.mjpg":
                return self._stream()

            file_path = os.path.realpath(os.path.join(STATIC, "index.html" if path == "/" else path.lstrip("/")))
            if not file_path.startswith(STATIC + os.sep) or not os.path.isfile(file_path):
                return self._send(404, {"error": "not found"})
            with open(file_path, "rb") as f:
                self._send(200, f.read(), mimetypes.guess_type(file_path)[0] or "application/octet-stream")

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last = None
            try:
                while True:
                    frame_id, jpg = presence.frame()
                    if jpg and frame_id != last:
                        last = frame_id
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode() + jpg + b"\r\n")
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "bad json"})

            if self.path == "/api/summon":
                report, face_mood, context = self._context()
                return self._send(200, ghost.summon(context, weather=report, face_mood=face_mood))
            if self.path == "/api/say":
                text = str(data.get("text", "")).strip()[:500]
                if not text:
                    return self._send(400, {"error": "empty"})
                return self._send(200, ghost.ask(text, self._context()[2]))
            self._send(404, {"error": "not found"})

    return ThreadingHTTPServer(("0.0.0.0", port), Handler)


if __name__ == "__main__":
    from presence import Presence
    from weather import Weather

    port = int(os.environ.get("SPIRIT_PORT", 8666))
    presence = Presence()
    presence.start()
    weather = Weather(os.environ.get("SPIRIT_CITY", "Norman, OK"))
    ghost = Ghost(cloud=CloudClient() if os.environ.get("SPIRIT_API_KEY") else None)
    print(f"[mirror] mode: {ghost.mode}")
    print(f"[mirror] the glass awaits at http://localhost:{port}")
    make_server(port, ghost, presence, weather).serve_forever()
