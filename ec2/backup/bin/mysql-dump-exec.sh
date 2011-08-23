#!/bin/bash

DUMP_FILE=/mnt/dump/$1-sizl.sql.gz

mysqldump --databases $1 | gzip > $DUMP_FILE
echo $DUMP_FILE
