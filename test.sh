#! /usr/bin/env bash

APP="$1"
VER=3.12

cd ./projects/$APP

command -v brew && brew install ffmpeg
pip install -r requirements.txt
pip install whispermlx

python$VER app.py &
