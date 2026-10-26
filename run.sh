#!/bin/sh
# Start the mirror. Packages unpacked into .pylib (by scripts/deploy-uno-q.sh) are
# used when the board has no pip; a system OpenCV from apt works too.
cd "$(dirname "$0")"
PYTHONPATH="$PWD/.pylib${PYTHONPATH:+:$PYTHONPATH}" exec python3 app.py
