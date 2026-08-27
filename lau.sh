#! /bin/bash

set -e

APPS="$(ls projects)"
ARG="$1"
OS=$(uname)
VER=3.12

test -n "$APPS"
test -n "$OS"
test -n "$VER"

echo $OS|grep -qv "^Linux$"

export VER

for PORT in 5030 5034 5005; do
  pids="$(lsof -i :$PORT|cut -f 2)"
  test -n "$pids" && for pid in "$pids"; do
    test -d /proc/$pid && kill -15 $pid
  done
done

purge_pip() {
  command -v deactivate &>/dev/null && deactivate || true
  find . -type d -iname "venv" | xargs rm -rf || true
  find . -type d -iname ".venv" | xargs rm -rf || true
  rm -rf $HOME/.cache/pip || true
  python$VER -m venv .venv
  source .venv/bin/activate
  test -n "$VIRTUAL_ENV"
  test -d "$VIRTUAL_ENV"
  export VIRTUAL_ENV
  pip install --upgrade pip &>/dev/null || true
}

direct_pip() {
  command -v deactivate &>/dev/null && deactivate || true
  test -d .venv || python$VER -m venv .venv
  source .venv/bin/activate || return
  test -n "$VIRTUAL_ENV"
  test -d "$VIRTUAL_ENV"
  export VIRTUAL_ENV
}

launch_apps() {
  for APP in $APPS; do
    test -n "$APP"
    bash utest.sh "$APP"
  done
}

warm=true
test -n "$ARG" && echo "$ARG"|grep -q "^--cold$" && warm=false
if $warm; then
  if direct_pip && launch_apps; then
    true
  else
    purge_pip && launch_apps
  fi
else
  purge_pip && launch_apps
fi

echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Done."
