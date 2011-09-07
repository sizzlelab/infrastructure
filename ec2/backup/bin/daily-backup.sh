#!/bin/bash

. $HOME/.profile

cd $HOME/infrastructure
git pull origin master

$HOME/infrastructure/ec2/backup/bin/daily-backup-snapshot.py

$HOME/infrastructure/ec2/backup/bin/daily-backup-mysql.py
