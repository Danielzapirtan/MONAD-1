#! /bin/bash

set -e

APPS="$(ls projects)"
if command -v uname &>/dev/null; then
  echo "$(uname) detected"
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
  VER=3.13
  command -v python$VER &>/dev/null || VER=3.14
else
  VER=3.12
fi
command -v python$VER &>/dev/null || VER=$(python3 --version|grep -o "\<3\.[[:digit:]]\+")
echo "Using python$VER"
export VER

echo -n "Trying to set up the virtual environment ... "
pkill -kill python$VER &>/dev/null || true
command -v deactivate && deactivate &>/dev/null || true
find . -type d -iname "*venv" | xargs rm -rf
rm -rf $HOME/.cache/pip
python$VER -m venv .venv
source .venv/bin/activate
export VIRTUAL_ENV
echo "Ok"

echo "Please wait ..."
for APP in $APPS; do
  LOG=/tmp/monad_$APP.log
  echo -n "Trying to launch $APP ... "
  if bash test.sh $APP &>$LOG; then
  	echo "Ok"
  else
	echo ""
	echo "Error log:"
	tail -n 20 $LOG
	false
  fi
done
echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Done."
