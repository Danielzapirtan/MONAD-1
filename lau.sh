#! /bin/bash

APPS="$(ls projects)"

brew install python-is-python3
pkill -kill python
pkill -kill python3.12
deactivate &>/dev/null || true
find . -type d -iname "*venv" | xargs rm -rf
rm -rf $HOME/.cache/pip
python -m venv .venv
export VIRTUAL_ENV
source .venv/bin/activate

for APP in $APPS; do
  bash utest.sh $APP || true
  echo "$APP launched"
done | cat -n
echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Launch terminated"
