#! /bin/bash

REPO="CorneliuBoboc/MONAD"

cd $HOME
rm -rf $REPO
git clone https://github.com/$REPO.git
cd $REPO
bash lau.sh

