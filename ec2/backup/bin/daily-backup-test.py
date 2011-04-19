#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

import subprocess


def main():
    for m in (0, 1, 2, 3, 4):
        for d in ("0", "1", "2", "3", "4", "5", "6"):
            exec_cmd(["./daily-backup.py", d])
        print '--------------------------'


def exec_cmd(args):
    try:
        print(" ".join(args))
        subprocess.check_call(args)
    except Exception, ex:
        print("abort: exec_cmd failed: %s" % ex)
        exit(-1)


if __name__ == '__main__':
    main()

