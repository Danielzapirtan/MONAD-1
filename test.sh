#! /usr/bin/env bash

VER=3.12
APP="$1"

cd ./projects/$APP

brew install ffmpeg
pip install -r requirements.txt
pip install whispermlx

python$VER app.py &
