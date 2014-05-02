#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Copyright (c) 2014 Mozilla Corporation
#
# Contributors:
# Anthony Verez averez@mozilla.com

import json
import logging
import os
import pyes
import pytz
import requests
import sys
from datetime import datetime
from datetime import timedelta
from configlib import getConfig, OptionParser
from logging.handlers import SysLogHandler
from dateutil.parser import parse
from pymongo import MongoClient

logger = logging.getLogger(sys.argv[0])


def loggerTimeStamp(self, record, datefmt=None):
    return toUTC(datetime.now()).isoformat()


def initLogger():
    logger.level = logging.INFO
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter.formatTime = loggerTimeStamp
    if options.output == 'syslog':
        logger.addHandler(
            SysLogHandler(
                address=(options.sysloghostname,
                    options.syslogport)))
    else:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(formatter)
        logger.addHandler(sh)


def toUTC(suspectedDate, localTimeZone="US/Pacific"):
    '''make a UTC date out of almost anything'''
    utc = pytz.UTC
    objDate = None
    if type(suspectedDate) == str:
        objDate = parse(suspectedDate, fuzzy=True)
    elif type(suspectedDate) == datetime:
        objDate = suspectedDate

    if objDate.tzinfo is None:
        objDate = pytz.timezone(localTimeZone).localize(objDate)
        objDate = utc.normalize(objDate)
    else:
        objDate = utc.normalize(objDate)
    if objDate is not None:
        objDate = utc.normalize(objDate)

    return objDate


def getFrontendStats(es):
    begindateUTC = toUTC(datetime.now() - timedelta(minutes=1))
    enddateUTC = toUTC(datetime.now())
    qDate = pyes.RangeQuery(qrange=pyes.ESRange('utctimestamp',
        from_value=begindateUTC, to_value=enddateUTC))
    qType = pyes.TermFilter('_type', 'mozdefhealth')
    qMozdef = pyes.TermsFilter('category', ['mozdef'])
    pyesresults = es.search(pyes.ConstantScoreQuery(pyes.BoolFilter(
        must=[qType, qDate, qMozdef])),
        indices='events')
    return pyesresults._search_raw()['hits']['hits']


def writeFrontendStats(data, mongo):
    for host in data:
        for key in host['_source']['details'].keys():
            # remove unwanted data
            if '.' in key:
                del host['_source']['details'][key]
        mongo.healthfrontend.insert(host['_source'])
        # print host['_source']['hostname']
        # print host['_source']['details']['loadaverage']
        # for key in host['_source']['details'].keys():
            # if key not in ('username', 'loadaverage'):
                # print key
                # print host['_source']['details'][key]['publish_eps']
                # print host['_source']['details'][key]['messages_ready']
                # print host['_source']['details'][key]['messages_unacknowledged']
                # if 'deliver_eps' in host['_source']['details'][key].keys():
                    # print host['_source']['details'][key]['deliver_eps']
        # print ''


def main():
    logger.debug('starting')
    logger.debug(options)
    try:
        es = pyes.ES(server=(list('{0}'.format(s) for s in options.esservers)))
        client = MongoClient(options.mongohost, options.mongoport)
        # use meteor db
        mongo = client.meteor
        writeFrontendStats(getFrontendStats(es), mongo)
    except Exception as e:
        logger.error("Exception %r sending health to mongo" % e)


def initConfig():
    # output our log to stdout or syslog
    options.output = getConfig('output', 'stdout', options.configfile)
    # syslog hostname
    options.sysloghostname = getConfig('sysloghostname', 'localhost',
        options.configfile)
    # syslog port
    options.syslogport = getConfig('syslogport', 514, options.configfile)

    options.mqservers = list(getConfig('mqservers', 'localhost',
        options.configfile).split(','))
    options.mquser = getConfig('mquser', 'guest', options.configfile)
    options.mqpassword = getConfig('mqpassword', 'guest', options.configfile)
    # port of the rabbitmq json management interface
    options.mqapiport = getConfig('mqapiport', 15672, options.configfile)

    # elastic search server settings
    options.esservers = list(getConfig('esservers', 'http://localhost:9200',
        options.configfile).split(','))
    options.mongohost = getConfig('mongohost', 'localhost', options.configfile)
    options.mongoport = getConfig('mongoport', 3001, options.configfile)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option(
        "-c",
        dest='configfile',
        default=sys.argv[0].replace('.py', '.conf'),
        help="configuration file to use")
    (options, args) = parser.parse_args()
    initConfig()
    initLogger()
    main()

