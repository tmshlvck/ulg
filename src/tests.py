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
import cherrypy

import config
import defaults

import ulg
import index

import sys
import re
import time

# main
if __name__=="__main__":
    r = config.routers[0]
#    print r.runCommand(r.listCommands()[0],[])

#    print "Test router 0 command 0 passed. \n\n"

    u = index.ULGCgi()
    print u.renderULGIndex(routerid=0,commandid=0,sessionid=None)

    print "Test ULG index passed. \n\n"

    rdr = u.renderULGAction(routerid=0,commandid=0,sessionid=None,**{})
    print "Test ULG run action passed. Rdr exc = %s \n\n" % str(rdr)
    m = re.compile('sessionid=([^"]+)"',re.M).search(rdr)
    if(m):
        sessionid = m.groups()[0]
        print "Test ULG run action passed with sessionid="+str(sessionid) + "\n\n"
    else:
        print "Failed  ULG run action.\n\n"
        sys.exit(0)

    print u.renderULGResult(sessionid=sessionid)
    print "Test ULG result passed 1st time. Sleeping 5 seconds."
    time.sleep(5)

    print u.renderULGResult(sessionid=sessionid)
    print "Test ULG result passed 2nd time. Sleeping 5 seconds."
    time.sleep(5)

    print u.renderULGResult(sessionid=sessionid)
    print "Test ULG result passed 3rd time. Finish."
