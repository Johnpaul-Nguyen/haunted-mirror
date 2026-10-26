"""Local AI: watches the camera and decides whether a mortal is sitting at the board.

Runs fully on-device (OpenCV face detector), so it needs no network. If OpenCV or
the camera is missing, presence is disabled and the UI falls back to "press Enter".
"""

import os
import sys
import threading
import time

try:
    import cv2
except ImportError:
    cv2 = None

ARRIVE_HITS = 3        # frames in a row with a face before the spirit wakes
LEAVE_SECONDS = 8.0    # seconds with no face before the spirit sleeps


class Presence:
    def __init__(self, camera_index=None):
        self.camera_index = int(camera_index if camera_index is not None else os.environ.get("SPIRIT_CAMERA", 0))
        self.enabled = False
        self.present = False
        self.faces = 0
        self.last_seen = 0.0
        self.jpeg = None
        self.error = None
        self._lock = threading.Lock()

    def start(self):
        if cv2 is None:
            self.error = "opencv not installed"
            print("[presence] OpenCV missing: presence disabled")
            return
        threading.Thread(target=self._run, daemon=True).start()

    def state(self):
        with self._lock:
            return {"enabled": self.enabled, "present": self.present, "faces": self.faces, "error": self.error}

    def frame(self):
        with self._lock:
            return self.jpeg

    def _open(self):
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.camera_index, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return cap

    def _run(self):
        if not hasattr(cv2, "CascadeClassifier"):
            self.error = "this OpenCV has no Haar detector (needs 4.x)"
            print(f"[presence] {self.error}: presence disabled")
            return
        detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        cap = self._open()
        if not cap.isOpened():
            self.error = f"camera {self.camera_index} not found"
            print(f"[presence] {self.error}: presence disabled")
            return
        self.enabled = True
        print(f"[presence] watching camera {self.camera_index}")
        hits = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.5)
                continue
            small = cv2.resize(frame, (320, 240))
            gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            faces = detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))
            now = time.time()
            hits = hits + 1 if len(faces) else 0

            # The "scrying glass": a red, grainy view with the spirit's gaze on each face.
            tinted = cv2.merge([gray // 4, gray // 5, gray])
            for (x, y, w, h) in faces:
                cv2.ellipse(tinted, (x + w // 2, y + h // 2), (w // 2 + 6, h // 2 + 10), 0, 0, 360, (40, 40, 255), 1)
            ok_jpg, jpg = cv2.imencode(".jpg", tinted, [cv2.IMWRITE_JPEG_QUALITY, 60])

            with self._lock:
                self.faces = len(faces)
                if len(faces):
                    self.last_seen = now
                if not self.present and hits >= ARRIVE_HITS:
                    self.present = True
                elif self.present and now - self.last_seen > LEAVE_SECONDS:
                    self.present = False
                if ok_jpg:
                    self.jpeg = jpg.tobytes()
            time.sleep(0.15)
