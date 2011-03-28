#!/bin/bash
#
# see: http://uec-images.ubuntu.com/ for list of published Canonical AMIs

# Could use this to check that a given image is avaliable
ec2-describe-images -o 099720109477  | grep "^IMAGE" | grep "ubuntu-images\/" | grep "machine" | perl -e 'for(<>) { @r = split /\t/;  print "$r[1], $r[7], $r[12], " . +( split /\//, $r[2] )[-1]; print "\n"; }' 
