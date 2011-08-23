#!/bin/bash

DUMP_DIR=/mnt/dump

if [ ! -d "$DUMP_DIR" ]; then
    mkdir /mnt/dump && chown cos.cos /mnt/dump
fi
