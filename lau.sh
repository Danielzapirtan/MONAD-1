#! /bin/bash

APPS="$(ls projects)"
ARCH=$(uname)
if echo $ARCH | grep -q "^Linux$"; then
  DEMO=true
else
  DEMO=false
fi

if $DEMO; then
  VER=3.14
else
  VER=3.12
fi
export DEMO VER

pkill -kill python$VER
deactivate &>/dev/null || true
find . -type d -iname "*venv" | xargs rm -rf
rm -rf $HOME/.cache/pip
python$VER -m venv .venv
export VIRTUAL_ENV
source .venv/bin/activate

for APP in $APPS; do
  bash test.sh $APP || true
  echo "$APP launched"
done
echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Launch terminated"
