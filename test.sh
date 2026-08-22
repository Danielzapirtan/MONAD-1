#! /usr/bin/env bash

APP="$1"

cd ./projects/$APP

if $DEMO; then
  sudo apt install -y ffmpeg
else
  brew install ffmpeg
fi

pip install -r requirements.txt
$DEMO || pip install whispermlx

python$VER app.py &
