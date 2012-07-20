#!/usr/bin/env python
#
# ULG - Universal Looking Glass
# by Tomas Hlavacek (tomas.hlavacek@nic.cz)
# last udate: June 21 2012
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
import os, sys
import random
import time
import pickle

import config
import defaults

import ulgmodel

### ULG cron script

class ULGCron:
    def __init__(self):
        pass

    def rescanRouters(self):
        for r in config.routers:
            r.rescanHook()

    def clearSessions(self):
        pass

    def run(self):
        ulgmodel.log("ULG cron run.")
        self.rescanRouters()
        self.clearSessions()
        ulgmodel.log("ULG cron finished.")


# main

if __name__=="__main__":
    sys.exit(ULGCron().run())
