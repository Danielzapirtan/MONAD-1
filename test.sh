#! /bin/bash

set -e

APP="$1"

test -n "$APP"
test -n "$DEMO"
test -n "$SECRET"
test -n "$VER"

cd ./projects/$APP

if $DEMO; then
  LOG=/tmp/ffmpeg_$SECRET.log
  if sudo apt install -y ffmpeg &>$LOG; then
    echo "Successfully installed ffmpeg"
  else
    echo ""
    echo "Failed to install ffmpeg."
    tail $LOG
    false
  fi
else
  LOG=/tmp/ffmpeg_$SECRET.log
  if brew install ffmpeg &>$LOG; then
    echo "Successfully installed ffmpeg"
  else
    echo ""
    echo "Failed to install ffmpeg."
    tail $LOG
    false
  fi
fi

LOG=/tmp/requirements_$SECRET.log
if pip install -r requirements.txt &>$LOG; then
  echo "Successfully installed requirements"
else
  echo ""
  echo "Failed to install python requirements"
  tail $LOG
  false
fi

if ! $DEMO; then
  if pip install whispermlx &>$LOG; then
    echo "Successfully installed whispermlx"
  else
    echo ""
    echo "Failed to install whispermlx"
    tail $LOG
    false
  fi
fi

LOG=/tmp/app_$SECRET.log
if ! python$VER app.py &>$LOG; then
  cat $LOG
  false
fi &
