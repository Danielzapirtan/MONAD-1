#! /usr/bin/env bash

set -e

APP="$1"

test -n $APP
test -n $DEMO
test -n $VER

cd ./projects/$APP

if $DEMO; then
  sudo apt install -y ffmpeg
else
  brew install ffmpeg
fi

pip install -r requirements.txt
$DEMO || pip install whispermlx

if ! python$VER app.py; then
  false
fi &
