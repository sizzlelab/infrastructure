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

MASTER_INSTANCE_ID = 'i-83be19f5'
DUMP_DATABASES = ['commonservices_production', 'research_production_alpha', 'kassi_production']
S3_BUCKET = 'sizl-db-dumps'

START_DELAY_SECS = 30
POLL_WAIT_SECS = 5
SLAVE_STATUS_TIMEOUT_SECS = 1800

# basically ../log/dump-exec.log relative to this file
LOG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), os.path.join('..', 'log', 'dump-exec.log')))

FROM_EMAIL_ADDRESS = 'dump-exec@sizl.org'
TO_EMAIL_ADDRESS = 'sizl-aws@hiit.fi'
EMAIL_WAIT_SECS = 10

CONFIG = {}
CONFIG_FILENAME = os.path.normpath(os.path.join(os.path.dirname(__file__), os.path.join('..', 'etc', 'dump-exec-config.json')))

BIN_DIR = os.path.normpath(os.path.dirname(__file__))

def backup():
    if not CONFIG['do_backup']:
        logging.info('backup not done, do_backup is False')
        return

    # stop slave in case it's active from a previous run
    exec_cmd(['mysqladmin', 'stop-slave'])

    # make sure the slave is linked to the master by internal IP address
    exec_cmd([os.path.join(BIN_DIR, 'mysql-link-master.sh'), MASTER_INSTANCE_ID], True)

    # start slave
    exec_cmd(['mysqladmin', 'start-slave'])

    # poll mysql until it has synchronized
    start_ts = time.time()
    while True:
        status = read_cmd([os.path.join(BIN_DIR, 'mysql-slave-status.sh')])
        logging.info("Slave is behind by: %s" % status)

        if status.strip() == '0':
            logging.info('database syncronized.')
            break

        # check for timeout
        if time.time() >= (start_ts + SLAVE_STATUS_TIMEOUT_SECS):
            logging.error('abort: database synchronization timeout')
            logging.info('--- dump-exec END (ABORT) ---')
            end(-1)

        time.sleep(POLL_WAIT_SECS)


    # stop slave
    exec_cmd(['mysqladmin', 'stop-slave'])

    # create the dump dir on instance storage (will be removed on shutdown)
    exec_cmd(['sudo', os.path.join(BIN_DIR, 'mk-dump-dir.sh')])

    # exec dump
    dump_files = []
    for db in DUMP_DATABASES:
        dump_file = read_cmd([os.path.join(BIN_DIR, 'mysql-dump-exec.sh'), db])
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
        logging.error("abort: dump-exec failed: %s" % ex)
        logging.info('--- dump-exec END (ABORT) ---')
        end(-21)


def exec_cmd(args, no_quit=False):
    try:
        logging.info(" ".join(args))
        subprocess.check_call(args)
    except Exception, ex:
        logging.error("abort: exec_cmd failed: %s" % ex)
        logging.info('--- dump-exec END (ABORT) ---')
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

    if CONFIG['do_shutdown']:
        # shut the machine down
        exec_cmd(['sudo', '/sbin/shutdown', '-h', 'now'])

    exit(code)


def load_config(**kwargs):
    global CONFIG

    # get the configuration
    # excepts a json encoded dict.
    ret = {}
    try:
        f = open(CONFIG_FILENAME)
        json_str = f.read()
        f.close()
        CONFIG = json.loads(json_str)
    except Exception, ex:
        logging.error("error: loading config failed: %s; assuming defaults: %s" % (ex, kwargs))

    # add defaults from keyword arguments
    for k,v in kwargs.items():
        if not k in CONFIG:
            CONFIG[k] = v
    
    logging.info("Using config: %s" % CONFIG)
    return CONFIG


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        filename=LOG_FILE,
                        format='%(asctime)s [%(threadName)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('--- dump-exec START ---')

    #read in configuration
    load_config(do_backup=True, do_shutdown=True)

    # delay a bit before starting
    logging.info("sleeping for %s secs..." % START_DELAY_SECS)
    time.sleep(START_DELAY_SECS)

    # execute the backup
    backup()
    logging.info('--- dump-exec END (OK) ---')

    # clean up and finish
    end(0)


