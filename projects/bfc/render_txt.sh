#! /bin/bash

ARG="$1"

cp "$ARG" myEpub.zip
mkdir -p myEpub
dir=$PWD
mv myEpub.zip myEpub
cd myEpub
unzip myEpub.zip
cd EPUB/xhtml
for n in $(ls [0-9]*.xhtml); do
	cat $n \
		| dos2unix \
		| grep "^.p.*p.$" \
		>> /tmp/tmp
done
cd $dir
rm -rf myEpub
cp /tmp/tmp output.txt
cat output.txt
echo "Done."
