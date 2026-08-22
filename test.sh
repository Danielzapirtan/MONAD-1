#! /usr/bin/env bash

set -e

APP="$1"

test -n "$APP"
test -n "$DEMO"
test -n "$VER"

cd ./projects/$APP

if $DEMO; then
  if sudo apt install -y ffmpeg; then
    echo -n "1 "
  else
    echo ""
    echo "Failed to install ffmpeg."
    false
  fi
else
  if brew install ffmpeg; then
     echo -n "1 "
   else
    echo ""
    echo "Failed to install ffmpeg."
     false
   fi
fi

if pip install -r requirements.txt; then
  echo -n "2 "
else
  echo ""
  echo "Failed to install python requirements"
  false
fi

if ! $DEMO; then
  if pip install whispermlx; then
    echo -n "3 "
  else
    echo ""
    echo "Failed to install whispermlx"
  fi
fi

if ! python$VER app.py; then
  false
fi &
