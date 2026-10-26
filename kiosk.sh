#!/bin/sh
# Start the mirror (if it isn't running) and show it full-screen on this display.
# Installed as a login autostart on the UNO Q by scripts/deploy-uno-q.sh --autostart.
cd "$(dirname "$0")"
pgrep -f '[p]ython3 app.py' >/dev/null || setsid -f ./run.sh > /tmp/mirror.log 2>&1 < /dev/null

# Wait up to 30 s for the server so Chromium doesn't open on an error page.
i=0
until python3 -c 'import urllib.request; urllib.request.urlopen("http://localhost:8666/api/state", timeout=1)' 2>/dev/null; do
  i=$((i + 1)); [ "$i" -ge 30 ] && break; sleep 1
done

exec chromium --kiosk --no-first-run --noerrdialogs --disable-infobars \
  --autoplay-policy=no-user-gesture-required --use-fake-ui-for-media-stream \
  "http://localhost:8666/?kiosk=1"
