#! /usr/bin/env bash

APP="$1"

cd ./projects/$APP

brew install ffmpeg
pip install -r requirements.txt
pip install whispermlx

python app.py &
