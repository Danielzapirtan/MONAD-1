#! /usr/bin/env bash

VER=3.14
APP="$1"

cd ./projects/$APP

sudo apt update
sudo apt install -y ffmpeg

pip install -r requirements.txt
python$VER app.py &
