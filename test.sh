#! /bin/bash

set -e

APP="$1"

test -n "$APP"
test -n "$DEMO"
test -n "$SECRET"
test -n "$VER"

cd ./projects/$APP

LOG=/tmp/ffmpeg_$SECRET.log
if $DEMO; then
  if sudo apt install -y ffmpeg &>$LOG; then
    echo "Successfully installed ffmpeg"
  else
    echo "Failed to install ffmpeg."
    tail $LOG
    false
  fi
else
  if brew install ffmpeg &>$LOG; then
    echo "Successfully installed ffmpeg"
  else
    echo "Failed to install ffmpeg."
    tail $LOG
    false
  fi
fi

LOG=/tmp/requirements_$SECRET.log
if pip install -r requirements.txt &>$LOG; then
  echo "Successfully installed requirements"
else
  echo "Failed to install python requirements"
  tail $LOG
  false
fi

LOG=/tmp/whispermlx_$SECRET.log
if ! $DEMO; then
  if pip install whispermlx &>$LOG; then
    echo "Successfully installed whispermlx"
  else
    echo "Failed to install whispermlx"
    tail $LOG
    false
  fi
fi

if false; then
LOG=/tmp/app_$SECRET.log
if ! python$VER app.py &>$LOG; then
  echo "Failed to launch $APP"
  tail $LOG
  false
else
  echo "Successfully launch $APP"
fi &
fi
