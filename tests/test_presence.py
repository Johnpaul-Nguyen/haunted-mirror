from presence import MoodTracker, PresenceTracker


def test_presence_needs_consecutive_hits_to_arrive():
    p = PresenceTracker(arrive_hits=3, leave_seconds=8)
    assert p.update(True, 0.0) is False
    assert p.update(False, 0.1) is False  # streak broken
    assert p.update(True, 0.2) is False
    assert p.update(True, 0.3) is False
    assert p.update(True, 0.4) is True


def test_presence_survives_short_gaps_then_leaves():
    p = PresenceTracker(arrive_hits=1, leave_seconds=8)
    p.update(True, 0.0)
    assert p.update(False, 5.0) is True   # looked away briefly
    assert p.update(False, 8.5) is False  # really gone


def test_presence_gap_resets_when_face_returns():
    p = PresenceTracker(arrive_hits=1, leave_seconds=8)
    p.update(True, 0.0)
    p.update(True, 7.0)
    assert p.update(False, 14.0) is True


def test_mood_unknown_until_enough_face_frames():
    m = MoodTracker(window=20, min_frames=5)
    for _ in range(4):
        m.update(face=True, smile=True, eyes=2)
    assert m.guess() is None


def test_mood_ignores_frames_without_face():
    m = MoodTracker(window=20, min_frames=5)
    for _ in range(10):
        m.update(face=False, smile=False, eyes=0)
    assert m.guess() is None


def test_mood_smiling():
    m = MoodTracker(window=20, min_frames=5)
    for i in range(10):
        m.update(face=True, smile=i % 2 == 0, eyes=2)
    assert m.guess() == "smiling"


def test_mood_tired_when_eyes_rarely_seen():
    m = MoodTracker(window=20, min_frames=5)
    for i in range(10):
        m.update(face=True, smile=False, eyes=1 if i == 0 else 0)
    assert m.guess() == "tired"


def test_mood_neutral():
    m = MoodTracker(window=20, min_frames=5)
    for _ in range(10):
        m.update(face=True, smile=False, eyes=2)
    assert m.guess() == "neutral"


def test_mood_window_forgets_old_frames():
    m = MoodTracker(window=10, min_frames=5)
    for _ in range(10):
        m.update(face=True, smile=True, eyes=2)
    for _ in range(10):
        m.update(face=True, smile=False, eyes=2)
    assert m.guess() == "neutral"


def test_mood_reset():
    m = MoodTracker(window=10, min_frames=5)
    for _ in range(10):
        m.update(face=True, smile=True, eyes=2)
    m.reset()
    assert m.guess() is None
