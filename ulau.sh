#! /bin/bash

APPS="$(ls projects)"

pkill -kill python3.14
for APP in $APPS; do
  bash utest.sh $APP &>/tmp/monad_$APP.log
  echo "$APP launched"
done 
echo "All apps have been launched"
echo "See them on ports 5030, 5034 and 5005"
echo "Launch terminated"
