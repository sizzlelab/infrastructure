#!/bin/bash

awk -v RS='--- daily-backup-mysql START ---' 'END{print RS,$0}' $1
