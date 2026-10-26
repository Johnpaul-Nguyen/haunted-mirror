# Spirit Board

A haunted Ouija board that tutors you. Sit in front of it and a spirit called
MORTIS wakes with a jump scare. Name any topic and it teaches you one idea at a
time, then quizzes you. The planchette spells its verdict across the board.
Get it wrong and it mocks you, then explains the right answer.

Built for Hacktoberfest 2026 on the Arduino UNO Q.

## Why it helps

Active recall (being quizzed) beats rereading notes. Most people skip it because
it's dull. MORTIS makes it hard to skip. It works for any subject, and it adapts
the next question to how you answered the last one.

## How the AI is split

| Part | Where it runs | What it does |
|---|---|---|
| Presence detection | On the board (OpenCV face detector) | Wakes the spirit when you sit down, sleeps it when you leave. No network needed. |
| Tutor | Cloud LLM (DigitalOcean Gradient by default) | Explains, quizzes and judges answers in character. |
| Offline spirit | On the board | Built-in quiz bank (computer science, science, history) for when there's no key or no Wi-Fi. |

The cloud side uses any OpenAI-compatible endpoint, so DigitalOcean, Ollama or
OpenAI all work by changing `.env`. If the cloud call fails mid-seance, the board
switches to the offline spirit instead of freezing.

## Hardware

- Arduino UNO Q (Qualcomm Dragonwing QRB2210 running Debian, STM32U585 MCU)
- USB camera
- Monitor, keyboard (and mouse to click past the veil)

## Run it on a laptop

Needs Python 3.10 or newer.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
cp .env.example .env                          # add your key, or leave blank for offline
.venv/bin/python app.py
```

Open http://localhost:8666, press any key to lift the veil (browsers need a key
press before they play sound), then sit in front of the camera or press Enter.

## Run it on the UNO Q

The UNO Q's Linux side is Debian on ARM64. Plug in the monitor, keyboard and
USB camera, open a terminal on the board (or SSH in), then:

```bash
sudo apt update && sudo apt install -y python3-opencv chromium git
git clone https://github.com/Johnpaul-Nguyen/spirit-board.git
cd spirit-board
cp .env.example .env && nano .env
python3 app.py &
chromium --kiosk --autoplay-policy=no-user-gesture-required http://localhost:8666
```

Use the apt OpenCV, not pip. It's prebuilt for ARM and saves a long compile. If the
camera isn't found, try `SPIRIT_CAMERA=1` in `.env` (`ls /dev/video*` lists them).

## Get a DigitalOcean key

1. Redeem your credit code in the DigitalOcean control panel (Billing).
2. Go to Agent Platform / Gradient AI, then Serverless Inference, and create a model access key.
3. Put it in `.env` as `SPIRIT_API_KEY`. Check the model list on that page and set
   `SPIRIT_MODEL` to one that's available (for example `llama3.3-70b-instruct` or `openai-gpt-oss-120b`).
4. Restart `app.py`. The bottom-left corner shows `CLOUD:<model>` when it's live.

## Controls

- Any key: lift the veil
- Enter (while asleep): summon without the camera
- Type and press Enter: answer or ask
- Type `goodbye`: end the seance

## Files

- `app.py`: web server and API, standard library only
- `spirit.py`: prompt, cloud client, offline quiz bank
- `presence.py`: camera face detection and the red "scrying glass" view
- `static/`: the board, planchette, jump scare and synthesised sound

## Not done yet

- The MCU side (STM32) is unused. The built-in LED matrix could show the
  spirit's eyes through the Arduino Bridge.
- Modulino sensors aren't wired in. A buzzer on summon or knob-controlled
  difficulty would be easy additions.
- Not yet tested on the UNO Q itself or against a live DigitalOcean key.
