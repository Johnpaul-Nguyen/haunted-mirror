#!/usr/bin/env bash
# Deploy the mirror to an Arduino UNO Q over USB (adb). Needs no network or sudo on
# the board: Python packages are downloaded here for ARM64 and unpacked there.
#
#   scripts/deploy-uno-q.sh          copy, unpack, run tests on the board
#   scripts/deploy-uno-q.sh --start  ...then (re)start the mirror on the board
#   scripts/deploy-uno-q.sh --autostart  ...and open it full-screen at every desktop login
#                                        (undo: rm ~/.config/autostart/haunted-mirror.desktop)
set -euo pipefail
export MSYS_NO_PATHCONV=1  # stop Git Bash rewriting /home/... into Windows paths

cd "$(dirname "$0")/.."
ADB="${ADB:-adb}"
command -v "$ADB" >/dev/null || ADB="$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe"
DEST=/home/arduino/haunted-mirror
CACHE=".deploy-cache"
PY="${PYTHON:-python}"
[ -x .venv/Scripts/python ] && PY=.venv/Scripts/python
[ -x .venv/bin/python ] && PY=.venv/bin/python

"$ADB" get-state >/dev/null 2>&1 || { echo "No board found. Check the cable carries data, then: $ADB devices"; exit 1; }

mkdir -p "$CACHE/wheels"
if [ -z "$(ls "$CACHE/wheels" 2>/dev/null)" ]; then
  echo "Downloading ARM64 packages..."
  "$PY" -m pip download -q "opencv-python-headless>=4.8,<5" numpy pytest \
    --platform manylinux_2_28_aarch64 --platform manylinux2014_aarch64 --platform manylinux_2_17_aarch64 \
    --python-version 3.13 --implementation cp --abi cp313 --only-binary=:all: -d "$CACHE/wheels"
fi

echo "Copying the committed project (git HEAD) to $DEST..."
git archive --format=tar -o "$CACHE/mirror.tar" HEAD
"$ADB" shell "mkdir -p $DEST/.pylib /tmp/mirror-wheels"
"$ADB" push "$CACHE/mirror.tar" /tmp/mirror.tar >/dev/null
"$ADB" push "$CACHE/wheels/." /tmp/mirror-wheels/ >/dev/null
[ -f .env ] && "$ADB" push .env "$DEST/.env" >/dev/null

# The board's clock may be wrong without network; silence tar's timestamp warnings.
"$ADB" shell "cd $DEST && tar -xmf /tmp/mirror.tar && chmod +x run.sh kiosk.sh && \
  for w in /tmp/mirror-wheels/*.whl; do python3 -m zipfile -e \"\$w\" .pylib/; done"

echo "Running tests on the board..."
"$ADB" shell "cd $DEST && PYTHONPATH=.pylib python3 -m pytest -q -p no:cacheprovider 2>&1 | tail -2"

if [ "${1:-}" = "--autostart" ]; then
  "$ADB" shell "mkdir -p ~/.config/autostart && printf '%s\n' '[Desktop Entry]' 'Type=Application' \
    'Name=Haunted Mirror' 'Exec=$DEST/kiosk.sh' 'X-GNOME-Autostart-enabled=true' \
    > ~/.config/autostart/haunted-mirror.desktop && chmod 644 ~/.config/autostart/haunted-mirror.desktop && \
    cat ~/.config/autostart/haunted-mirror.desktop"  # adb's umask is 000; don't leave a login command world-writable
  echo "Autostart installed: the mirror opens full-screen when someone logs in on the board."
fi

if [ "${1:-}" = "--start" ] || [ "${1:-}" = "--autostart" ]; then
  # '[p]ython3' so pkill doesn't match (and kill) this very shell command.
  "$ADB" shell "pkill -f '[p]ython3 app.py' || true; cd $DEST && setsid -f ./run.sh > /tmp/mirror.log 2>&1 < /dev/null; sleep 4; tail -3 /tmp/mirror.log"
  echo "Started. Log: $ADB shell tail -f /tmp/mirror.log"
  echo "View it from the laptop: $ADB forward tcp:8667 tcp:8666, then open http://localhost:8667"
fi
