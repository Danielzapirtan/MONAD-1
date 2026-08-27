#! /bin/bash

set -e

APPS="$(ls projects)"
OS=$(uname)
VER=3.13

test -n "$APPS"
test -n "$OS"
test -n "$VER"

echo $OS|grep -q "^Linux$"

export VER

for PORT in 5030 5034 5005; do
  for pid in $(lsof -i :$PORT|cut -f 2); do
    kill -15 $pid
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
  echo "Ok"
}

direct_pip() {
  command -v deactivate &>/dev/null && deactivate || true
  test -d .venv || python$VER -m venv .venv
  source .venv/bin/activate
  test -n "$VIRTUAL_ENV"
  test -d "$VIRTUAL_ENV"
  export VIRTUAL_ENV
  echo "Ok"
}

launch_apps() {
  for APP in $APPS; do
    test -n "$APP"
    bash test.sh "$APP"
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
