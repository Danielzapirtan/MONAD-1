#! /bin/bash

set -e

APP="$1"

test -n "$APP"
test -n "$VER"

cd ./projects/$APP

if echo "$APP"|grep -qv "^bfc$"; then
  command -v ffmpeg &>/dev/null || brew install ffmpeg &>/dev/null
fi
pip install -r requirements.txt &>/dev/null
if echo "$APP"|grep -q "^diarix$"; then
  command -v whispermlx &>/dev/null || pip install whispermlx &>/dev/null
fi

python$VER app.py & pid=$!
sleep 20
test -d /proc/$pid

