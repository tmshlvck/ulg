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
import os, sys
import random

import config
import defaults

import ulgmodel
import ulg
import ulgcisco

import sys
import re
import time
import traceback


def testRouterCommand(router=0,command=0,params=[]):
    r = config.routers[router]
    try:
        if(not r.runCommand(r.listCommands()[command],params,ulg.DecoratorHelper())):
            print "WARN: Outpit of test running command "+str(command)+" on router "+str(router)+" with parameters:"+str(params)+" is empty."
            return False

    except Exception as e:
        print "FAIL: Test running command "+str(command)+" on router "+str(router)+" with parameters:"+str(params)+".\n  Exception="+str(e)
        return False

    print "OK: Test running command "+str(command)+" on router "+str(router)+" with parameters:"+str(params)
    return True


def testULGIndex(routerid=0,commandid=0,sessionid=None):
    try:
        u = ulg.ULGCgi()
        c = u.renderULGIndex(routerid,commandid,sessionid)
        if(c):
            print "OK: Test render ULG CGI index"
            return True
        else:
            print "WARN: Test render ULG CGI index is empty!"
            return False
        
    except Exception as e:
        print "FAIL: Test render ULG CGI index.\n Exception="+str(e)
        return False


def testULGAction(routerid=0,commandid=0,sessionid=None,maxtimes=10,interval=5,**params):
    try:
        u = ulg.ULGCgi()
        rdr = u.renderULGAction(routerid=0,commandid=0,sessionid=None,**params)
        m = re.compile('sessionid=([^"]+)"',re.M).search(rdr)
        if(m):
            sessionid = m.groups()[0]
            print "OK(1/2): Test ULG run action passed with sessionid="+str(sessionid)
        else:
            print "FAILED ULG run action. No session ID returned."
            return False
    except Exception as e:
        print "FAILED ULG run action.\n  Exception="+str(e)
        return False

    i=0
    while(i<maxtimes):
        if(re.compile("refresh",re.M).search(u.renderULGResult(sessionid=sessionid))):
            print "Test ULG result is not complete. Waiting another 5 seconds."
            time.sleep(interval)
            i+=1
        else:
            print "OK(2/2): Test ULG result is complete."
            return True

    print "FAIL: Test ULG result is not complete after "+str(maxtimes)
    return False


def testULGSessions(sessionid=None):
    try:
        s1 = ulg.Session(sessionid,routerid=1,commandid=2,parameters={'baba':'bubu'},result='reeesult')
        sid = s1.getSessionId()
        s2 = ulg.Session.load(sid)
        if(s1.getSessionId() == s2.getSessionId() and s1.getRouterId() == s2.getRouterId()):
            print "OK: Test sessions."
            return True
        else:
            print "WARN: Test sessions failed!"
            return False
        
    except Exception as e:
        print "FAIL: Test sessions.\n  Exception="+str(e)
        return False

def testULGLock():
    c = ulg.ULGCgi()

    def cleanup(c):
        for i in range(0,defaults.usage_limit):
            c.decreaseUsage()

    for i in range(0,defaults.usage_limit):
        if not c.increaseUsage():
            print """FAIL: Test lock. Increase usage rejected me while it should let me it.
(It can be effect of a real ULG running concurrently to tests."""
            return False
    if(c.increaseUsage()):
        print "FAIL: Test lock. Increase usage accepted overlimit."
        cleanup(c)
        return False

    c.decreaseUsage()

    if(not c.increaseUsage()):
        print """FAIL: Test lock. Increase usage rejected me while it should let me it.
(It can be effect of a real ULG running concurrently to tests."""
        cleanup(c)
        return False

    cleanup(c)
    print "OK: Test lock."
    return True

def testULGRunParameter(router=0,command=4,params=['91.210.16.1']):
    r = config.routers[router]
    try:
        if(not r.runCommand(r.listCommands()[command],params,ulg.DecoratorHelper())):
            print "WARN: Output of test running command "+str(command)+" on router "+str(router)+" with parameters:"+str(params)+" is empty."
            return False

    except Exception as e:
        print "FAIL: Test running command "+str(command)+" on router "+str(router)+" with parameters:"+str(params)+".\n  Exception="+str(e)
        print traceback.format_exc()
        return False

    print "OK: Test running command "+str(command)+" on router "+str(router)+" with parameters:"+str(params)
    return True

def testULGLog(testmessage="Test message no. 1."):
    try:
        ulgmodel.log(testmessage)
        print "OK: Logging test. Check logfile for message: "+testmessage
        return True
    except Exception as e:
        print "FAIL: Logging test."
        print traceback.format_exc()
        return False

def testULGRescan():
    try:
        for r in config.routers:
            r.rescanHook()

        print "OK: Test running rescan."
        return True
    except Exception as e:
        print "FAIL: Test running rescan.\n  Exception="+str(e)
        print traceback.format_exc()
        return False

def testULGPersistentStorage():
    try:
        ps = ulgmodel.PersistentStorage.load()
        ps.set('test','teststring')
        ps.save()

        ps2 = ulgmodel.PersistentStorage.load()
        if(ps2.get('test') == 'teststring'):
            ps2.delete('test')
            if(ps2.get('test') == None):
                print "OK: Test persistent storage."
                return True
            else:
                print "FAIL: Test persistent storage: Delete performed no effect."
                return False
        else:
            print "FAIL: Test persistent storage: Set performed no effect."
            return False
    except Exception as e:
        print "FAIL: Test persistent storage.\n  Exception="+str(e)
        print traceback.format_exc()
        return False  

def testULGCiscoParser(header,cisco_input,expect):
    try:
        res = ulgcisco.matchCiscoBGPLines(header,cisco_input)

#        print "DEBUG: Cisco parser input: " + str(cisco_input)
#        print "DEBUG: Cisco parser output: " + str(res)

        if(res == expect):
            print "OK: Test Cisco parser."
            return True
        else:
            print "DEBUG: Cisco parser input: " + str(cisco_input)
            print "DEBUG: Cisco parser output: " + str(res)
            print "FAIL: Test Cisco parser. Wrong output."
            return False

    except Exception as e:
        print "FAIL: Test Cisco parser.\n  Exception="+str(e)
        print traceback.format_exc()
        return False  


def testULGCiscoParser1():
    header = "Stat Network          Next_Hop            Metric LocPrf Weight Path"
    cisco_input = """ *>  62.109.128.0/19  0.0.0.0                  0         32768 i
 *>  91.199.207.0/24  217.31.48.86                 1024      0 44672 i
 *>  91.224.58.0/23   217.31.48.70           100   1024      0 50833 i
 *>  93.170.16.0/21   217.31.48.70           100   1024      0 50833 i
 *>  188.227.128.0/19 0.0.0.0                  0         32768 i
 *>  217.31.48.0/20   0.0.0.0                  0         32768 i"""

    expect = [['*>', '62.109.128.0/19', '0.0.0.0', '0', '', '32768', 'i'],
              ['*>', '91.199.207.0/24', '217.31.48.86', '', '1024', '0', '44672 i'],
              ['*>', '91.224.58.0/23', '217.31.48.70', '100', '1024', '0', '50833 i'],
              ['*>', '93.170.16.0/21', '217.31.48.70', '100', '1024', '0', '50833 i'],
              ['*>', '188.227.128.0/19', '0.0.0.0', '0', '', '32768', 'i'],
              ['*>', '217.31.48.0/20', '0.0.0.0', '0', '', '32768', 'i']]


    return testULGCiscoParser(header,cisco_input.splitlines(),expect)

def testULGCiscoParser2():
    header = "Stat Network          Next_Hop            Metric LocPrf Weight Path"
    cisco_input = " *   195.226.217.0    62.109.128.9                           0 51278 i"
    expect = [['*', '195.226.217.0', '62.109.128.9', '', '', '0', '51278 i']]

    return testULGCiscoParser(header,cisco_input.splitlines(),expect)

def testULGCiscoParser3():
    header = "Stat Network          Next_Hop            Metric LocPrf Weight Path"
    cisco_input = """ *>  2001:67C:278::/48
                       2001:1AB0:7E1F:1:230:48FF:FE8C:A192
                                                    1024      0 51278 i
 *>  2001:1AB0::/32   ::                       0         32768 i
 *>  2A01:8C00::/32   ::                       0         32768 i"""
    expect = [['*>', '2001:67C:278::/48', '2001:1AB0:7E1F:1:230:48FF:FE8C:A192', '', '1024', '0', '51278 i'],
              ['*>', '2001:1AB0::/32', '::', '0', '', '32768', 'i'],
              ['*>', '2A01:8C00::/32', '::', '0', '', '32768', 'i']]

    return testULGCiscoParser(header,cisco_input.splitlines(),expect)



#####################################
results = []

def runTest(result):
    global results
    results.append(result)

def reportResults():
    global results
    tests = len(results)
    failed = [ridx for (ridx,r) in enumerate(results) if r == False]
    passed = [ridx for (ridx,r) in enumerate(results) if r == True]

    print """\n***** Results *****
Tests pased: %d/%d
Tests failed: %d/%d""" % (len(passed),tests,len(failed),tests)
    print "Failed numbers: "+str(failed)+"\n"

# main
if __name__=="__main__":
    runTest(testRouterCommand(router=0,command=0,params=[]))
    runTest(testULGRunParameter(router=0,command=4,params=['91.210.16.1']))
    runTest(testULGIndex(routerid=0,commandid=0,sessionid=None))
    runTest(testULGAction(routerid=0,commandid=0,sessionid=None,maxtimes=10,interval=5,**{}))
    runTest(testULGSessions())
    runTest(testULGLock())
    runTest(testULGLog())
    runTest(testULGRescan())
    runTest(testULGPersistentStorage())
    runTest(testULGCiscoParser1())
    runTest(testULGCiscoParser2())
    runTest(testULGCiscoParser3())


    reportResults()
