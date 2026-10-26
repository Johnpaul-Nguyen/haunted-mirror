"""Local AI: the camera sees who stands at the mirror and guesses their mood.

Runs fully on-device with OpenCV's Haar detectors, so no image ever leaves the
board. If OpenCV or the camera is missing, presence is disabled and the UI
falls back to "press Enter".
"""

import os
import sys
import threading
import time
from collections import deque

try:
    import cv2
except ImportError:
    cv2 = None


def find_camera(candidates, open_fn, tries=5):
    """First device that actually delivers a frame. Some open fine and never do
    (on the UNO Q, /dev/video0 and video1 are the Qualcomm video codec)."""
    for index in candidates:
        cap = open_fn(index)
        if cap.isOpened() and any(cap.read()[0] for _ in range(tries)):
            return index, cap
        cap.release()
    return None, None


class PresenceTracker:
    """Debounces raw face detections into 'someone is here' / 'they left'."""

    def __init__(self, arrive_hits=3, leave_seconds=8.0):
        self.arrive_hits = arrive_hits
        self.leave_seconds = leave_seconds
        self.present = False
        self.hits = 0
        self.last_seen = 0.0

    def update(self, has_face, now):
        self.hits = self.hits + 1 if has_face else 0
        if has_face:
            self.last_seen = now
        if not self.present and self.hits >= self.arrive_hits:
            self.present = True
        elif self.present and now - self.last_seen > self.leave_seconds:
            self.present = False
        return self.present


class MoodTracker:
    """A rough mood guess from the last few frames: smiling, tired or neutral.

    Smile: the smile detector fires on a good share of frames.
    Tired: a face is there but open eyes are rarely found (heavy or closed lids).
    """

    def __init__(self, window=20, min_frames=5):
        self.frames = deque(maxlen=window)
        self.min_frames = min_frames

    def reset(self):
        self.frames.clear()

    def update(self, face, smile, eyes):
        if face:
            self.frames.append((smile, eyes > 0))

    def guess(self):
        if len(self.frames) < self.min_frames:
            return None
        n = len(self.frames)
        smiles = sum(1 for s, _ in self.frames if s) / n
        eyes_seen = sum(1 for _, e in self.frames if e) / n
        if smiles >= 0.35:
            return "smiling"
        if eyes_seen < 0.25:
            return "tired"
        return "neutral"


class Presence:
    def __init__(self, camera_index=None):
        chosen = camera_index if camera_index is not None else os.environ.get("SPIRIT_CAMERA", "")
        self.candidates = [int(chosen)] if str(chosen).strip() else list(range(6))
        self.camera_index = None
        self.enabled = False
        self.error = None
        self.tracker = PresenceTracker()
        self.mood = MoodTracker()
        self.faces = 0
        self.jpeg = None
        self.frame_id = 0
        self._lock = threading.Lock()

    def start(self):
        if cv2 is None:
            self.error = "opencv not installed"
        elif not hasattr(cv2, "CascadeClassifier"):
            self.error = "this OpenCV has no Haar detector (needs 4.x)"
        else:
            threading.Thread(target=self._run, daemon=True).start()
            return
        print(f"[presence] {self.error}: presence disabled")

    def state(self):
        with self._lock:
            return {
                "enabled": self.enabled,
                "present": self.tracker.present,
                "faces": self.faces,
                "mood": self.mood.guess() if self.tracker.present else None,
                "error": self.error,
            }

    def frame(self):
        with self._lock:
            return self.frame_id, self.jpeg

    def _run(self):
        cascade = lambda name: cv2.CascadeClassifier(cv2.data.haarcascades + name)
        face_det = cascade("haarcascade_frontalface_default.xml")
        self.profile_det = cascade("haarcascade_profileface.xml")
        smile_det = cascade("haarcascade_smile.xml")
        eye_det = cascade("haarcascade_eye_tree_eyeglasses.xml")  # the plain one misses eyes behind glasses

        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

        def open_camera(index):
            cap = cv2.VideoCapture(index, backend)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            return cap

        self.camera_index, cap = find_camera(self.candidates, open_camera)
        if cap is None:
            self.error = f"no working camera (tried {self.candidates})"
            print(f"[presence] {self.error}: presence disabled")
            return
        self.enabled = True
        print(f"[presence] watching camera {self.camera_index}")

        count = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.5)
                continue
            frame = cv2.flip(cv2.resize(frame, (640, 480)), 1)  # a mirror shows you reversed
            count += 1
            if count % 2 == 0:  # detect on every other frame to keep the mirror smooth
                self._detect(frame, face_det, smile_det, eye_det)
            ok_jpg, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok_jpg:
                with self._lock:
                    self.jpeg = jpg.tobytes()
                    self.frame_id += 1
            time.sleep(0.03)

    def _detect(self, frame, face_det, smile_det, eye_det):
        # 480 px wide: 320 missed tilted, blurry or backlit faces in testing.
        gray = cv2.equalizeHist(cv2.cvtColor(cv2.resize(frame, (480, 360)), cv2.COLOR_BGR2GRAY))
        faces = face_det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
        smile, eyes = False, 0
        if not len(faces):
            # Turned away? The profile detector only sees one side, so try both.
            faces = self.profile_det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
            if not len(faces):
                faces = self.profile_det.detectMultiScale(cv2.flip(gray, 1), scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
            with self._lock:
                self.faces = len(faces)
                self.tracker.update(len(faces) > 0, time.time())
                if not self.tracker.present:
                    self.mood.reset()
            return  # a side view is presence, but too little to read mood from
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            lower = gray[y + h // 2:y + h, x:x + w]
            upper = gray[y:y + h // 2, x:x + w]
            smile = len(smile_det.detectMultiScale(lower, scaleFactor=1.7, minNeighbors=20)) > 0
            eyes = len(eye_det.detectMultiScale(upper, scaleFactor=1.1, minNeighbors=6))
        with self._lock:
            was_present = self.tracker.present
            self.faces = len(faces)
            if not self.tracker.update(len(faces) > 0, time.time()):
                self.mood.reset()
            elif not was_present:
                self.mood.reset()
            self.mood.update(face=len(faces) > 0, smile=smile, eyes=eyes)
