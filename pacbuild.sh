#! /bin/bash

set -e

gcc -o pac pac.c
echo "Instalati pac in folderul /usr/local/bin?"
echo "Acest lucru ar putea necesita privilegii de superutilizator!"
echo -n "y/n? "
read ans

echo "$ans" | grep -q "^y$"

sudo install -m 755 -s pac /usr/local/bin
echo "Instalat ok"
