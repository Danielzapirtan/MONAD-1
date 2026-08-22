#! /usr/bin/env bash

APP="$1"

cd ./projects/$APP

sudo apt update
sudo apt install -y ffmpeg

pip install -r requirements.txt
python app.py &
