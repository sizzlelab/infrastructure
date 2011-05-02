#!/bin/bash

. /home/cos/.profile
ec2-ami-tools/bin/ec2-bundle-vol -u 7747-2178-7864 -c /home/cos/.aws/cert-ATW57ZBEHKPMQNTZNWTF7XORQPREVTCE.pem -k /home/cos/.aws/pk-ATW57ZBEHKPMQNTZNWTF7XORQPREVTCE.pem -r i386 -d /mnt -e /mnt
