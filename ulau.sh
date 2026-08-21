#! /bin/bash

APPS="$(ls projects)"
VER=3.14

pkill -kill python$VER
deactivate &>/dev/null || true
find . -type d -iname "*venv" | xargs rm -rf
rm -rf $HOME/.cache/pip
python$VER -m venv .venv
export VIRTUAL_ENV
source .venv/bin/activate

for APP in $APPS; do
  bash utest.sh $APP &>/tmp/monad_$APP.log
  echo "$APP launched"
done 
echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Launch terminated"
