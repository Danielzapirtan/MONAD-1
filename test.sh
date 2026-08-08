#! /usr/bin/env bash

VER=3.12
APP="$1"

cd ./projects/$APP

brew install python@$VER
if test -z $VIRTUAL_ENV; then
	test -d venv || python$VER -m venv venv
	source venv/bin/activate
	export VIRTUAL_ENV
fi
brew install ffmpeg
pip install -r requirements.txt
pip install mlx-whisper
python$VER app.py

