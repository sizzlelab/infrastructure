#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

'''
A script to help restore to a given backup snapshot.
Takes:
    - a period name PPP, e.g. 'Mon', 'Tue', 'Weekly1', etc
    - an instance type for the restore, e.g. 'c1.medium'
    - an IP address for the instance (probably the same elastic IP address of the failed instance)

    - this will:
        - bring up a new instance of the given type
        - attach bak-dat-PPP -> /dev/sdh
        - attach bak-sys-PPP -> /dev/sda1
    - pause and wait for verification that this has been successful
    - associate the IP address with the new instance

It is left to the admin to terminate/etc the old instance as a separate manual process.
'''

'''
TODO:
'''

import sys
import os
import re
import time
from datetime import date
import subprocess
import logging

DEFAULT_KERNEL_ID = 'aki-4deec439'
DEFAULT_AMI_ID = 'ami-fb9ca98f'
DEFAULT_KEYPAIR = 'sizl-ubuntu1'
DEFAULT_GROUP = 'sizl-web'
DEFAULT_REGION = 'eu-west-1b'

# backup period constants
MON = 0
TUE = 1
WED = 2
THU = 3
FRI = 4
SAT = 5
SUN = 6
WK1 = 7
WK2 = 8
WK3 = 9
PERIOD_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Weekly1', 'Weekly2', 'Weekly3']

# backup type constants
TYPE_DAT = 0
TYPE_SYS = 1
VOL_IDS = ['vol-f0109d99', 'vol-560a873f']
TYPE_PREFIXES = ['dat-', 'sys-']

# metadata tag constants
META_TAG_NAME = 'Name'
META_TAG_PREFIX = 'bak-'


def main(restore_period, instance_type, ip_address):
    # convert restore period string into numeric representation
    try:
        restore_period = PERIOD_NAMES.index(restore_period)
    except Exception, ex:
        logging.error("abort: no such restore period: %s" % restore_period)
        logging.info('--- restore END (ABORT) ---')
        exit(-5)

    # get information about current tags
    try:
        data = read_cmd(["ec2-describe-tags"])
        tags = parse_tags(data)
    except Exception, ex:
        logging.error("abort: could not get tags: %s" % ex)
        logging.info('--- restore END (ABORT) ---')
        exit(-1)
    
    # check that there is a snapshot for the given restore period
    dat_tag = get_tag(restore_period, TYPE_DAT)
    sys_tag = get_tag(restore_period, TYPE_SYS)
    if not tags.has_key(dat_tag):
        logging.error("abort: no such snapshot found: %s" % dat_tag)
        exit(-2)

    if not tags.has_key(sys_tag):
        logging.error("abort: no such snapshot found: %s" % sys_tag)
        exit(-3)

    # get information about the target snapshots
    try:
        data = read_cmd(["ec2-describe-snapshots", tags[dat_tag], tags[sys_tag]])
        snapshot_info = parse_snapshots(data)
    except Exception, ex:
        logging.error("abort: could not get snapshot info: %s" % ex)
        logging.info('--- restore END (ABORT) ---')
        exit(-4)

    # form the block device specs
    dat_snapshot_id = tags[dat_tag]
    sys_snapshot_id = tags[sys_tag]

    dat_snapshot_size = snapshot_info[tags[dat_tag]]
    sys_snapshot_size = snapshot_info[tags[sys_tag]]

    sdh  = "'/dev/sdh=%s:%s:false'" % (dat_snapshot_id, dat_snapshot_size)
    sda1 = "'/dev/sda1=%s:%s:false'" % (sys_snapshot_id, sys_snapshot_size)

    # confirm action
    print """
    Will bring up the following instance:
          kernelId:\t%s
           keypair:\t%s
             group:\t%s
            region:\t%s
              type:\t%s
          /dev/sdh:\t%s
         /dev/sda1:\t%s
    """ % (DEFAULT_KERNEL_ID, DEFAULT_KEYPAIR, DEFAULT_GROUP, DEFAULT_REGION, instance_type, sdh, sda1)

    # request confirmation to proceed
    confirm("Do you want to continue?")

    # register the sys snapshot as an AMI
    logging.info("Registering AMI from sys snapshot %s.." % sys_snapshot_id)
    ts =  time.strftime('%Y-%m-%d %H.%M.%S', time.gmtime())
    ami_id = read_cmd(["ec2-register", "--root-device-name", "/dev/sda1", "--kernel", DEFAULT_KERNEL_ID, "-n", "Restored from %s at %s" % (sys_snapshot_id, ts), "-s", sys_snapshot_id], 'IMAGE\tami-[0-9a-z]+')
    ami_id = ami_id.strip().split("\t")[-1]

    # bring up the new instance, also with the /dev/sdh volume
    logging.info("Bringing up new instance..")
    instance_id_re = 'INSTANCE\ti-[0-9a-z]+' 
    data = read_cmd(["ec2-run-instances", ami_id, "-k", DEFAULT_KEYPAIR, "-g", DEFAULT_GROUP, "-z", DEFAULT_REGION, "-t", instance_type], instance_id_re)
    try:
        new_instance_id = re.search(instance_id_re, data).group(0).split("\t")[-1]
    except Exception, ex:
        logging.error("abort: could not get new AMI id: %s" % ex)
        logging.info('--- restore END (ABORT) ---')
        exit(-8)
    
    # wait for manual confirmation that this has succeeded
    confirm("Please confirm that the instance has started")

    # create a new volume from the data snapshot
    logging.info("Creating volume from data snapshot %s.." % dat_snapshot_id)
    volume_id_re = 'VOLUME\tvol-[0-9a-z]+' 
    data = read_cmd(["ec2-create-volume", "--snapshot", dat_snapshot_id, "-z", DEFAULT_REGION])
    try:
        dat_volume_id = re.search(volume_id_re, data).group(0).split("\t")[-1]
    except Exception, ex:
        logging.error("abort: could not get new volume id: %s" % ex)
        logging.info('--- restore END (ABORT) ---')
        exit(-9)
    
    # wait for manual confirmation that this has succeeded
    confirm("Please confirm that the volume has been created")

    # attach this volume to /dev/sdh
    logging.info("Attaching volume %s to /dev/sdh .." % dat_snapshot_id)
    exec_cmd(["ec2-attach-volume", dat_volume_id, "-i", new_instance_id, "-d", "/dev/sdh"])
    
    # wait for manual confirmation that this has succeeded
    confirm("Please confirm that the volume has been attached")

    # associate given IP address with the new instance
    logging.info("Associating IP address [%s] with new instance %s..." % (ip_address, new_instance_id))
    exec_cmd(["ec2-associate-address", ip_address, "-i", new_instance_id])


#--- helpers --
def read_cmd(args, result_re=None):
    try:
        logging.info(" ".join(args))
        (data, err) = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
        if err:
            raise Exception(err)

        elif result_re:
            if not re.search(result_re, data):
                raise Exception("Result does not match %s: %s, %s" % (result_re, err, data)) 

        return data
    except Exception, ex:
        logging.error("abort: read_cmd failed: %s" % ex)
        logging.info('--- restore END (ABORT) ---')
        exit(-21)


def exec_cmd(args):
    try:
        logging.info(" ".join(args))
        subprocess.check_call(args)
    except Exception, ex:
        logging.error("abort: exec_cmd failed: %s" % ex)
        logging.info('--- restore END (ABORT) ---')
        exit(-22)


def confirm(s):
    instr = raw_input("%s (y or n): " % s)
    if not instr == 'y':
        logging.info('--- restore END (USER ABORT) ---')
        exit(2)


def get_tag(period, backup_type):
    return "%s%s%s" % (META_TAG_PREFIX, TYPE_PREFIXES[backup_type], PERIOD_NAMES[period])


def parse_tags(data):
    '''
    Parse the raw output from ec2-describe-tags into an dict.
    Only take into account the tag with the name META_TAG_NAME
    TAG     snapshot        snap-8a5211e3   Name    Mon
    '''
    ret = {}
    for line in data.split('\n'):
        if line == '':
            next

        fields = line.split('\t')
        if fields[0] == 'TAG' and fields[1] == 'snapshot':
            if fields[3] == META_TAG_NAME and fields[4].startswith(META_TAG_PREFIX):
                ret[fields[4]] = fields[2]

    return ret


def parse_snapshots(data):
    '''
    Parse the raw output from ec2-describe-snapshots into an dict.
    At the moment is just matches a snapshot-id with a volume size in Gib.
    SNAPSHOT        snap-d4efacbd   vol-f0109d99    completed       2011-04-19T12:52:34+0000        100%    774721787864    10    ec2-consistent-snapshot
    '''
    ret = {}
    for line in data.split('\n'):
        if line == '':
            next

        fields = line.split('\t')
        if fields[0] == 'SNAPSHOT':
            ret[fields[1]] = fields[7]

    return ret


if __name__ == '__main__':
    import optparse

    # get the command line arguments
    parser = optparse.OptionParser()
    parser.add_option('-p', '--restore-period', dest='restore_period', metavar='RESTORE_PERIOD', help='Which backup to restore to, e.g. "Mon", "Tue", "Weekly1", etc')
    parser.add_option('-t', '--instance-type', dest='instance_type', metavar='INSTANCE_TYPE', help='EC2 instance type for the restored instance, e.g. "c1.medium"')
    parser.add_option('-i', '--ip-address', dest='ip_address', metavar='IP_ADDRESS', help='IP address which will be associated with the new instance. Probably the elastic IP address of the failed instance.')

    options, args = parser.parse_args()
    if len(args) != 0:
        parser.error("Unknown arguments %s\n" % args)
 
    if options.restore_period == None:
        parser.error("No restore period specified")
    else:
        restore_period = options.restore_period
 
    if options.instance_type == None:
        parser.error("No instance type specified")
    else:
        instance_type = options.instance_type
 
    if options.ip_address == None:
        parser.error("No IP address specified")
    else:
        ip_address = options.ip_address


    # set up logging
    logging.basicConfig(level=logging.DEBUG,
                        # basically ../log/restore.log relative to this file
                        #filename=os.path.normpath(os.path.join(os.path.dirname(__file__), os.path.join('..', 'log', 'restore.log'))),
                        stream=sys.stderr,
                        format='%(asctime)s [%(threadName)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('--- restore START ---')

    # execute
    main(restore_period, instance_type, ip_address)
    logging.info('--- restore END (OK) ---')

