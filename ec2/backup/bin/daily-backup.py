#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

'''
A daily backup script which works on the basis of ec2 volume snapshots.
It uses tags to track meta-data about the snapshots, and is thus not reliant on an external source of metadata.
Each day:
    - if a backup exists for this day of the week
        - if the day is "sun"
            - delete snapshot "weekly3"
            - mv "weekly2" -> "weekly3"
            - mv "weekly1" -> "weekly2"
            - mv "sun" -> "weekly1"
        - else
            - delete snapshot for this day of the week

    - make new snapshot for this day of week
'''

'''
TODO:
    O need to figure out a way to test this?
    O need much more extensive logging to be able to
        - keep track of what has been done, and when
        - fix things if backup fails
    - do we need notifications of some kind (email?) if backup fails?
    - review the try/except situation to make it certain that we get some log/notification of failure
    - at the moment only doing data volume backups, what about the system volume?
    - once a snapshot has been taken, should we poll to make sure that it has completed?
        - after timeout -> raise errror
'''

import sys
import os
from datetime import date
import subprocess
import re
import logging

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

DUMPER_INSTANCE_ID = 'i-65c34713'


def main(weekday):
    # get information about current tags
    try:
        data = read_cmd(["ec2-describe-tags"])
        tags = parse_tags(data)
    except Exception, ex:
        logging.error("abort: could not get tags: %s" % ex)
        logging.info('--- daily-backup END (ABORT) ---')
        exit(-1)

    # do backup [FIXME: at the moment just TYPE_DAT]
    for vol_type in [TYPE_DAT, TYPE_SYS]:
        today_tag = get_tag(weekday, vol_type)
        logging.info("Making snapshot for %s: %s" % (vol_type, today_tag))
        if weekday == SUN:
            wk1_tag = get_tag(WK1, vol_type)
            wk2_tag = get_tag(WK2, vol_type)
            wk3_tag = get_tag(WK3, vol_type)

            # delete the oldest weekly and shift the others down
            if tags.has_key(wk3_tag):
                exec_cmd(["ec2-delete-snapshot", tags[wk3_tag]])
            if tags.has_key(wk2_tag):
                exec_cmd(["ec2-create-tags", tags[wk2_tag], "--tag", "%s=%s" % (META_TAG_NAME, wk3_tag)])
            if tags.has_key(wk1_tag):
                exec_cmd(["ec2-create-tags", tags[wk1_tag], "--tag", "%s=%s" % (META_TAG_NAME, wk2_tag)])
                
            # move existing SUN backup to become new WK1
            if tags.has_key(today_tag):
                exec_cmd(["ec2-create-tags", tags[today_tag], "--tag", "%s=%s" % (META_TAG_NAME, wk1_tag)])
        else:
            if tags.has_key(today_tag):
                # there is an existing snapshot for this day, delete it
                exec_cmd(["ec2-delete-snapshot", tags[today_tag]])

        # create new snapshot and add today's tag
        take_snapshot(vol_type, today_tag)

    # start up a dumper instance
    exec_cmd(["ec2-start-instances", DUMPER_INSTANCE_ID])


#--- helpers --
def take_snapshot(vol_type, tag):
    if vol_type == TYPE_SYS:
        snap_id = read_cmd(["sudo", "ec2-consistent-snapshot", "--aws-credentials-file", "/home/cos/.aws/sizl-aws@hiit.fi", "--region", "eu-west-1", VOL_IDS[TYPE_SYS]], '^snap-[0-9a-z]+')
        #snap_id = read_cmd(["ec2-create-image", CURRENT_INSTANCE_ID, "-n", tag, "-d", "Backup AMI image", "--no-reboot"], 'IMAGE\tami-[0-9a-z]+')
        #snap_id = snap_id.strip().split("\t")[-1]
    else:
        snap_id = read_cmd(["sudo", "ec2-consistent-snapshot", "--aws-credentials-file", "/home/cos/.aws/sizl-aws@hiit.fi", "--region", "eu-west-1", "--freeze-filesystem", "/data", "--mysql", "--mysql-defaults-file", "/home/cos/.mysql/ec2-snapshot-mysql.cnf", VOL_IDS[TYPE_DAT]], '^snap-[0-9a-z]+')

    # TODO: poll here to make sure that snapshot has been completed, or timeout to error?

    # attach the tag
    exec_cmd(["ec2-create-tags", snap_id.strip(), "--tag", "%s=%s" % (META_TAG_NAME, tag)])

def read_cmd(args, result_re=None):
    try:
        logging.info(" ".join(args))
        (data, err) = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
        if result_re:
            if not re.match(result_re, data):
                raise Exception("Result does not match %s: %s, %s" % (result_re, err, data)) 

        return data
    except Exception, ex:
        logging.error("abort: read_cmd failed: %s" % ex)
        logging.info('--- daily-backup END (ABORT) ---')
        exit(-2)


def exec_cmd(args):
    try:
        logging.info(" ".join(args))
        subprocess.check_call(args)
    except Exception, ex:
        logging.error("abort: exec_cmd failed: %s" % ex)
        logging.info('--- daily-backup END (ABORT) ---')
        exit(-3)


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
        if fields[0] == 'TAG':
            if fields[1] == 'snapshot' or fields[1] == 'image':
                if fields[3] == META_TAG_NAME and fields[4].startswith(META_TAG_PREFIX):
                    ret[fields[4]] = fields[2]

    return ret


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        # basically ../log/daily-backup.log relative to this file
                        filename=os.path.normpath(os.path.join(os.path.dirname(__file__), os.path.join('..', 'log', 'daily-backup.log'))),
                        format='%(asctime)s [%(threadName)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('--- daily-backup START ---')

    # weekday is today, or optionallly can be overidden
    weekday = date.today().weekday()
    if len(sys.argv) > 1:
        try:
            weekday = int(sys.argv[1])
            if weekday < 0 or weekday > 6:
                raise ValueError()
        except ValueError:
            logging.error("Invalid int input: %s" % sys.argv[1])
            exit(-4)

    main(weekday)
    logging.info('--- daily-backup END (OK) ---')

