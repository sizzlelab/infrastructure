#!/bin/bash

. $HOME/.profile

cd $HOME/infrastructure
git pull origin master

$HOME/infrastructure/ec2/backup/bin/dump-exec.py
