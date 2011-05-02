#!/bin/bash

mysql -e "show slave status\G" | grep "Seconds_Behind_Master" | sed 's/^[^:]*: //'
