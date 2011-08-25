#!/bin/bash

. $HOME/.profile

cd $HOME
git pull origin master

$HOME/infrastructure/ec2/backup/bin/daily-backup.py
