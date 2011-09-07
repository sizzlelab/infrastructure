#!/bin/bash

OUT_FILE="$2/$1.sql.gz"

mysqldump --single-transaction --quick $1 | gzip > $OUT_FILE
echo $OUT_FILE
