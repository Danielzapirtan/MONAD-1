#! /bin/bash

ARG="$1"

dir=$PWD
rm -rf myEpub
cp "$ARG" myEpub.zip
mkdir -p myEpub
mv myEpub.zip myEpub
cd myEpub
unzip myEpub.zip
cd EPUB/xhtml
cat [0-9]*.xhtml >> /tmp/tmp1
cat /tmp/tmp1 \
	| dos2unix \
	| grep "^<p>" \
	>> /tmp/tmp2
cat /tmp/tmp2 \
	| sed -e "s/^<p>//g" \
	| sed -e "s|</p>$||g" \
	>> /tmp/tmp3
cd $dir
cp /tmp/tmp3 output.txt
echo "Done."

