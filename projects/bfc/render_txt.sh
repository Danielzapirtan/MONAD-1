#! /bin/bash

ARG="$1"

cp "$ARG" myEpub.zip
mkdir -p myEpub
dir=$pwd
mv myEpub.zip myEpub
cd myEpub
unzip myEpub.zip
cd myEpub/EPUB/xhtml
for n in $(ls [0-9]*.xhtml); do
  cat $n|grep "^.p.*p.$" |cut -b 4,$-4>>$dir/output.txt
done
echo "Done."
