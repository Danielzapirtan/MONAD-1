#! /bin/bash

set -e

APP="$1"

test -n "$APP"
test -n "$VER"

cd ./projects/$APP

if echo "$APP"|grep -qv "^bfc$"; then
  command -v ffmpeg &>/dev/null || apt install -y ffmpeg &>/dev/null
fi
pip install -r requirements.txt &>/dev/null

python$VER app.py & pid=$!
sleep 20
test -d /proc/$pid

