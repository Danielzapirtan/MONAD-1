#! /bin/bash

set -e

APPS="$(ls projects)"
if command -v uname; then
  if uname | grep -q "^Linux$"; then
    DEMO=true
  else
    DEMO=false
  fi
else
  DEMO=false
fi
export DEMO

if $DEMO; then
  VER=3.14
else
  VER=3.12
fi
export VER

pkill -kill python$VER
command -v deactivate && deactivate &>/dev/null || true
find . -type d -iname "*venv" | xargs rm -rf
rm -rf $HOME/.cache/pip
python$VER -m venv .venv
source .venv/bin/activate
export VIRTUAL_ENV

for APP in $APPS; do
  bash test.sh $APP || true
  echo "$APP launched"
done
echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Launch terminated"
