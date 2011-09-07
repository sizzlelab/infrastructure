#!/bin/bash

if [ ! -d "$1" ]; then
    mkdir $1 && chown cos.cos $1
fi
