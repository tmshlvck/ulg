#!/usr/bin/env python
#
# ULG - Universal Looking Glass
# (C) 2012 CZ.NIC, z.s.p.o.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Imports
import os, os.path, sys
import random
import time, datetime
import pickle
import re

import config
import defaults

import ulgmodel

### ULG cron script

SESSION_FILE_REGEX='^ulg-.*\.session$'
LOGFILE_LIMIT=1048576

class ULGCron:
    def __init__(self):
        pass

    def rescanRouters(self):
        for r in config.routers:
            r.rescanHook()

    def clearSessions(self):
        sre = re.compile(SESSION_FILE_REGEX)
        for file in os.listdir(defaults.session_dir):
            if sre.match(file):
                fp = defaults.session_dir+'/'+file

                now = datetime.datetime.now()
                if(datetime.datetime.fromtimestamp(os.path.getmtime(fp)) < now+datetime.timedelta(hours=-1)):
                    ulgmodel.log('Removing file '+fp)
                    try:
                        os.unlink(fp)
                    except OSError as e:
                        ulgmodel.log('Error while removing file '+fp+' '+str(e))
                else:
                    ulgmodel.log('Not removing file '+fp+' because it is not at least 1 hour old.')

    def clearLog(self):
        try:
            if(os.stat(defaults.log_file).st_size > LOGFILE_LIMIT):
                os.unlink(defaults.log_file)
        except OSError as e:
            ulgmodel.log('Error while checking/removing logfile '+defaults.log_file+' '+str(e))
        ulgmodel.log("Logfile removed due to excessive size. Please set logrotate to keep the file size below "+str(LOGFILE_LIMIT)+" bytes.")

    def run(self):
        ulgmodel.log('ULG cron run.')
        self.clearLog()
        self.rescanRouters()
        self.clearSessions()
        ulgmodel.log('ULG cron finished.')


# main

if __name__=="__main__":
    sys.exit(ULGCron().run())
