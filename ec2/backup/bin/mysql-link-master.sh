#!/bin/bash

MASTER_PUBLIC_DNS=`ec2-describe-instances $1 | egrep ^INSTANCE | cut -f4`
MASTER_IP=`dig +short $MASTER_PUBLIC_DNS`
mysql -e "CHANGE MASTER TO MASTER_HOST='$MASTER_IP'"
