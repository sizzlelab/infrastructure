#!/bin/bash

awk -v RS='--- dump-exec START ---' 'END{print RS,$0}' $1
