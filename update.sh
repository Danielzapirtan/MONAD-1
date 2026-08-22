#! /bin/bash

REPO="MONAD"

cd $HOME
rm -rf $REPO
git clone https://github.com/CorneliuBoboc/$REPO.git
cd $REPO
bash lau.sh

