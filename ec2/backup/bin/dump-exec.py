#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

import os
import time
import subprocess
import re
import logging
import smtplib
from email.mime.text import MIMEText

DUMP_DATABASES = ['commonservices_production', 'research_production_alpha', 'kassi_production']
S3_BUCKET = 'sizl-db-dumps'

POLL_WAIT_SECS = 5
SLAVE_STATUS_TIMEOUT_SECS = 1800

# basically ../log/dump-exec.log relative to this file
LOG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), os.path.join('..', 'log', 'dump-exec.log')))

FROM_EMAIL_ADDRESS = 'dump-exec@sizl.org'
TO_EMAIL_ADDRESS = 'sizl-aws@hiit.fi'
EMAIL_WAIT_SECS = 10


def main():
    # start slave
    exec_cmd(['mysqladmin', 'start-slave'])

    # poll mysql until it has synchronized
    start_ts = time.time()
    while True:
        status = read_cmd(['/home/cos/bin/mysql-slave-status.sh'])
        if status.strip() == '0':
            logging.info('database syncronized.')
            break

        # check for timeout
        if time.time() == (start_ts + SLAVE_STATUS_TIMEOUT_SECS):
            logging.error('abort: database synchronization timeout')
            logging.info('--- dump-exec END (ABORT) ---')
            end(-1)

        time.sleep(POLL_WAIT_SECS)


    # stop slave
    exec_cmd(['mysqladmin', 'stop-slave'])

    # exec dump
    dump_file = read_cmd(['/home/cos/bin/mysql-dump-exec.sh'] + DUMP_DATABASES)

    # copy dumps to S3
    exec_cmd(['s3cmd', 'put', dump_file.strip(), "s3://%s/" % S3_BUCKET])


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


def exec_cmd(args):
    try:
        logging.info(" ".join(args))
        subprocess.check_call(args)
    except Exception, ex:
        logging.error("abort: exec_cmd failed: %s" % ex)
        logging.info('--- dump-exec END (ABORT) ---')
        end(-22)


def end(code=0):
    log = read_cmd(['cat', LOG_FILE])

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

    # shut the machine down
    exec_cmd(['sudo', '/sbin/shutdown', '-h', 'now'])

    exit(code)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        filename=LOG_FILE,
                        format='%(asctime)s [%(threadName)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('--- dump-exec START ---')
    main()
    logging.info('--- dump-exec END (OK) ---')

    end(0)
