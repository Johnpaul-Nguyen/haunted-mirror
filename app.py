"""Spirit Board: a haunted Ouija tutor. Run `python app.py` and open http://localhost:8666"""

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from presence import Presence
from spirit import Spirit

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")
PORT = int(os.environ.get("SPIRIT_PORT", 8666))

spirit = Spirit()
presence = Presence()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if "/api/state" not in self.path and "/api/scry" not in self.path:
            super().log_message(fmt, *args)

    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            return self._send(200, {"presence": presence.state(), "mode": spirit.mode, "score": spirit.score})
        if path == "/api/scry.jpg":
            jpg = presence.frame()
            return self._send(200, jpg, "image/jpeg") if jpg else self._send(404, {"error": "no frame"})

        file_path = os.path.normpath(os.path.join(STATIC, "index.html" if path == "/" else path.lstrip("/")))
        if not file_path.startswith(STATIC) or not os.path.isfile(file_path):
            return self._send(404, {"error": "not found"})
        with open(file_path, "rb") as f:
            self._send(200, f.read(), mimetypes.guess_type(file_path)[0] or "application/octet-stream")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})

        if self.path == "/api/summon":
            return self._send(200, spirit.summon())
        if self.path == "/api/ask":
            text = str(data.get("text", "")).strip()[:500]
            if not text:
                return self._send(400, {"error": "empty"})
            return self._send(200, spirit.ask(text))
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    presence.start()
    print(f"[spirit] mode: {spirit.mode}")
    print(f"[spirit] the board awaits at http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
