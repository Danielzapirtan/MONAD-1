#! /usr/bin/env bash

VER=3.14
APP="$1"

cd ./projects/$APP

if test -z $VIRTUAL_ENV; then
	test -d venv || python$VER -m venv venv
	source venv/bin/activate
	export VIRTUAL_ENV
fi

sudo apt update
sudo apt install -y ffmpeg

pip install -r requirements.txt
python$VER app.py

