#!/usr/bin/env python
# -*- coding: utf-8 -*-

# process-spot-price-history.py
# process the output of the AWS API call ec2-describe-spot-price-history
#
# Konrad Markus <konker@gmail.com>
#

import sys
import json
from datetime import datetime, timedelta

PRICE   = 1
DATE    = 2
TYPE    = 3
PRODUCT = 4
ZONE    = 5

HIGH = 'high'
LOW  = 'low'
MEAN = 'mean'

TS_FORMAT = "%Y-%m-%dT%H:%M:%S"

def main(filename, on_demand_price):
    data = {}

    with open(filename) as f:
        line = f.readline()
        while line:
            (label, price, ts, type, product, zone) = line.strip().split("\t")
            if not data.get(product, False):
                data[product] = {}

            if not data[product].get(type, False):
                data[product][type] = {}

            if not data[product][type].get(ts, False):
                data[product][type][ts] = {}

            data[product][type][ts][zone] = float(price)

            line = f.readline()

    # get the highs for each day sorted by ts
    highs = {}
    n = 0
    total = 0
    for product in data.keys():
        for type in data[product].keys():
            tss = data[product][type].keys()
            tss.sort()
            cur_ts = None
            prices = None
            
            for ts in tss:
                if not ts[:10] == cur_ts:
                    if prices:
                        highs[cur_ts] = max(prices)
                        total = total + highs[cur_ts]
                        n = n + 1

                    cur_ts = ts[:10]
                    prices = []
                    for zone in data[product][type][ts].keys():
                        prices.append(float(data[product][type][ts][zone]))

            highs[cur_ts] = max(prices)
            total = total + highs[cur_ts]
            n = n + 1

    # print out highs with on-demand price and mean price
    avg = total / n
    tss = highs.keys()
    tss.sort()
    for ts in tss:
        print "%s\t%s\t%s\t%s" % (ts, on_demand_price, highs[ts], avg)


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]))

