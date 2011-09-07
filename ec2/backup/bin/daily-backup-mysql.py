#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

import os
import time
import subprocess
import re
import logging
import json
import smtplib
from email.mime.text import MIMEText

DUMP_DIR='/mnt/dump'
DUMP_DATABASES = ['commonservices_production', 'research_production_alpha', 'kassi_production']
S3_BUCKET = 'sizl-db-dumps'

# basically ../log/daily-backup-mysql.log relative to this file
LOG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), os.path.join('..', 'log', 'daily-backup-mysql.log')))

FROM_EMAIL_ADDRESS = 'daily-backup-mysql@sizl.org'
TO_EMAIL_ADDRESS = 'sizl-aws@hiit.fi'
EMAIL_WAIT_SECS = 10

BIN_DIR = os.path.normpath(os.path.dirname(__file__))

def backup():
    # create the dump directory
    exec_cmd(['sudo', os.path.join(BIN_DIR, 'mk-dump-dir.sh'), DUMP_DIR])

    # exec dump
    dump_files = []
    for db in DUMP_DATABASES:
        dump_file = read_cmd([os.path.join(BIN_DIR, 'mysql-dump-exec.sh'), db, DUMP_DIR])
        dump_files.append(dump_file.strip())

    # copy dumps to S3
    for f in dump_files:
        exec_cmd(['s3cmd', 'put', f, "s3://%s/" % S3_BUCKET])


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
        logging.error("abort: daily-backup-mysql failed: %s" % ex)
        logging.info('--- daily-backup-mysql END (ABORT) ---')
        end(-21)


def exec_cmd(args, no_quit=False):
    try:
        logging.info(" ".join(args))
        subprocess.check_call(args)
    except Exception, ex:
        logging.error("abort: exec_cmd failed: %s" % ex)
        logging.info('--- daily-backup-mysql END (ABORT) ---')
        if not no_quit:
            end(-22)


def end(code=0):
    log = read_cmd([os.path.join(BIN_DIR, 'get-last-log.sh'), LOG_FILE])

    msg = MIMEText(log)
    msg['Subject'] = 'The contents of %s' % LOG_FILE
    msg['From'] = FROM_EMAIL_ADDRESS
    msg['To'] = TO_EMAIL_ADDRESS

    try:
        # Send the message via our own SMTP server, but don't include the
        # envelope header.
        s = smtplib.SMTP('localhost')
        s.sendmail(FROM_EMAIL_ADDRESS, [TO_EMAIL_ADDRESS], msg.as_string())
        s.quit()
    except Exception, ex:
        logging.error("error: sendmail failed: %s" % ex)
        exit(-23)

    time.sleep(EMAIL_WAIT_SECS)

    exit(code)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        filename=LOG_FILE,
                        format='%(asctime)s [%(threadName)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('--- daily-backup-mysql START ---')

    # execute the backup
    backup()
    logging.info('--- daily-backup-mysql END (OK) ---')

    # clean up and finish
    end(0)



