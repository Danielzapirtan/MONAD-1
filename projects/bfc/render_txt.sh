#! /bin/bash

ARG="$1"

cp "$ARG" myEpub.zip
mkdir -p myEpub
dir=$PWD
mv myEpub.zip myEpub
cd myEpub
unzip myEpub.zip
cd EPUB/xhtml
cat [0-9]*.xhtml \
	| grep "^.p.*p.$" \
	>> /tmp/tmp
cd $dir
rm -rf myEpub
cp /tmp/tmp output.txt
cat output.txt
echo "Done."
