# Haunted Mirror

A mirror with a ghost in it who checks on you every day. Stand in front of it
and VESPER wakes with a jump scare. She tells you what she sees in your face,
gives you the weather and what to wear, then asks how you really are. Talk to
her by voice or keyboard. She listens and, if you seem low, gives you one small,
concrete thing to do.

Built for Hacktoberfest 2026 on the Arduino UNO Q.

## Why it helps

People who live alone can go a whole day without anyone asking how they are.
Vesper asks, every time you walk past. She is creepy on purpose, which makes the
check-in fun instead of clinical, but underneath the act she cares.

If someone mentions self-harm or suicide, the server drops the ghost act and
gives the 988 Suicide and Crisis Lifeline. That check is plain code, not the AI
model, so it runs even offline and can't be talked out of it.

## How the AI is split

| Part | Runs on | Does |
|---|---|---|
| Presence | Board (OpenCV YuNet face detector, `models/`, MIT; Haar fallback) | Wakes Vesper when you arrive, sleeps her when you leave |
| Mood guess | Board (OpenCV smile + eye detectors) | Rough guess: smiling, tired or neutral. No image leaves the board |
| Conversation | Cloud LLM (DigitalOcean Gradient by default) | The check-in itself, in character |
| Offline ghost | Board | Scripted check-in when there's no key or no Wi-Fi |
| Weather | Open-Meteo (free, no key) | Forecast and outfit advice for your city |
| Voice | Browser speech APIs | Speech in and out, with keyboard as the fallback |

## Hardware

- Arduino UNO Q (Qualcomm Dragonwing QRB2210 running Debian, STM32U585 MCU)
- USB camera (with a mic, for voice)
- Monitor with speakers, keyboard

## Run it on a laptop

Needs Python 3.10+.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
cp .env.example .env                          # set SPIRIT_CITY; add a key or leave blank for offline
.venv/bin/python app.py
```

Open http://localhost:8666 in Chrome, press any key to pull back the cloth
(browsers need a key press before they play sound), then stand in front of the
camera or press Enter.

## Run it on the UNO Q

**Over USB, no network needed (tested).** Plug the board into the laptop with a
data cable, then from the laptop:

```bash
scripts/deploy-uno-q.sh --start
```

It copies the committed project over adb, unpacks ARM64 OpenCV and numpy into
`.pylib` (the board has no pip and `sudo` needs a password), runs the tests on
the board and starts the mirror. To see it from the laptop:
`adb forward tcp:8667 tcp:8666`, then open http://localhost:8667.

To show it on the board's own monitor, log in on the board's desktop, then:

```bash
adb shell "DISPLAY=:0 chromium --kiosk --autoplay-policy=no-user-gesture-required http://localhost:8666 >/dev/null 2>&1 &"
```

Without Wi-Fi the board runs the offline ghost with no weather and no voice
input. Plug a USB camera into the board for presence and mood; it's found
automatically (the board's own `/dev/video0` and `video1` are its video codec,
not cameras).

**With Wi-Fi and sudo**, the classic install also works:

```bash
sudo apt update && sudo apt install -y python3-opencv chromium speech-dispatcher espeak-ng git
git clone https://github.com/Johnpaul-Nguyen/haunted-mirror.git
cd haunted-mirror
cp .env.example .env && nano .env
python3 app.py &
chromium --kiosk --autoplay-policy=no-user-gesture-required http://localhost:8666
```

Use the apt OpenCV, not pip: it's prebuilt for ARM. `espeak-ng` gives Chromium a
voice to speak with. If the camera isn't found, set `SPIRIT_CAMERA=1`
(`ls /dev/video*` lists them).

**Voice input on the board is the risky part.** Chromium's speech recognition
sends audio to Google and doesn't work in every Linux build. If it fails, the
mirror says so, hides the mic button and keeps working by keyboard.

## Get a DigitalOcean key

1. Redeem your credit code in the DigitalOcean control panel (Billing).
2. Gradient AI → Serverless Inference → create a model access key.
3. Put it in `.env` as `SPIRIT_API_KEY`. Set `SPIRIT_MODEL` to a model listed on
   that page (tested: `deepseek-v4.1-flash`, fast, cheap and keeps the reply format).
4. Restart `app.py`. The bottom-left corner shows `CLOUD:<model>` when it's live.

## Controls

- Any key: pull back the cloth
- Enter (while asleep): wake her without the camera
- F2 or the mic button: speak. After you speak, she listens again once she finishes replying
- Type and press Enter: reply by keyboard
- Say or type `goodbye`: end the visit

## Tests

```bash
.venv/bin/python -m pytest          # weather, presence/mood, ghost, safety, HTTP server
node --test tests/logic.test.js     # browser logic: state machine, voice helpers
```

The camera loop, the real speech APIs and the cloud model can't be unit tested.
They were checked by hand in the browser.

## Files

- `app.py`: web server, API and the MJPEG mirror stream (standard library only)
- `ghost.py`: Vesper's prompt, safety check, cloud client and offline script
- `presence.py`: camera loop, presence and mood tracking
- `weather.py`: Open-Meteo forecast and outfit advice
- `static/logic.js`: browser logic with no DOM, tested by Node
- `static/mirror.js`, `mirror.css`, `index.html`: the mirror, ghost, sound and voice

## Not done yet

- Not tested on the UNO Q itself or with a live DigitalOcean key.
- The STM32 MCU and the Modulino sensors are unused.
- The mood guess is rough: lighting, glasses and head angle all fool it.
