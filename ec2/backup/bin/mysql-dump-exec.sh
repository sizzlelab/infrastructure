#!/bin/bash

DUMP_FILE=/home/cos/dump/sizl-production.sql.gz

mysqldump --databases $@ | gzip > $DUMP_FILE
echo $DUMP_FILE
