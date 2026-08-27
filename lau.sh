#! /bin/bash

set -e

need() {
  CMD="$1"
  if ! command -v "$CMD" &>/dev/null; then
    echo "Please install command $CMD"
    false
  fi
}
export -f need

need uname

OS=$(uname)
ARCH=$(uname -m)
: ${DEMO:=false}

need mktemp

APPS="$(ls projects)"
test -n "$APPS"
TEMPDIR="$(mktemp)"
test -n "$TEMPDIR"
export TEMPDIR

if $DEMO; then
  VER=3.13
  if echo $ARCH|grep -q "^aarch64$"; then
    VER=3.14
  fi
else
  VER=3.12
fi
command -v python$VER &>/dev/null || VER=$(python3 --version|grep -o "\<3\.[[:digit:]]\+")
test -n "$VER"
echo "Using python$VER"
need python$VER
export VER

purge_pip() {
  echo -n "Trying to purge the virtual environment ... "
  need pkill
  pkill -kill python$VER &>/dev/null || true
  command -v deactivate &>/dev/null && deactivate || true
  find . -type d -iname "venv" | xargs rm -rf
  find . -type d -iname ".venv" | xargs rm -rf
  rm -rf $HOME/.cache/pip
  python$VER -m venv .venv
  source .venv/bin/activate
  test -n "$VIRTUAL_ENV"
  export VIRTUAL_ENV
  need pip
  pip install --upgrade pip &>/dev/null || true
  echo "Ok"
}

direct_pip() {
  echo -n "Trying to set up the virtual environment ... "
  command -v deactivate &>/dev/null && deactivate || true
  test -d .venv || python$VER -m venv .venv
  source .venv/bin/activate
  test -n "$VIRTUAL_ENV"
  export VIRTUAL_ENV
  need pip
  pip install --upgrade pip &>/dev/null || true
  echo "Ok"
}

launch_apps() {
  echo "Please wait ..."
  for APP in $APPS; do
    test -n "$APP"
    LOG=$TEMPDIR/monad_$APP.log
    test -n "$LOG"
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
}

direct_pip
if ! launch_apps; then
  purge_pip
  launch_apps
fi

echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Done."
