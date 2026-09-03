#! /bin/bash

myRC=$HOME/.zshrc
myAliases=$HOME/.zsh_aliases

test -f $myAliases || {
  echo "test -f $myAliases && source $myAliases" >>$myRC
  cp zsh_aliases $myAliases
}

