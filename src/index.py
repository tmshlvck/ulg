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
from genshi.template import TemplateLoader
from genshi.core import Markup
import cgi
import cgitb; cgitb.enable()
import random
import time
import md5
import pickle
import threading

# Apache mod_wsgi hack of import directory
#if __name__.startswith('_mod_wsgi_'):
#    sys.path.reverse()
#    sys.path.append(os.path.dirname(__file__))
#    sys.path.reverse()

import config
import defaults

import ulg

### CGI output handler

class Session(object):
    def __init__(self,sessionid=None,routerid=None,commandid=None,parameters=None,result=None,finished=False):
        if(sessionid == None):
            self.sessionid = self.__genSessionId__()
        else:
            self.sessionid=sessionid

        self.routerid=routerid
        self.commandid=commandid
        self.parameters=parameters
        self.result=result
        self.finished=finished

        self.save()

    def __genSessionId__(self):
        return md5.new(str(time.time())+str(random.randint(1,1000000))).hexdigest()

    @staticmethod
    def getSessionFileName(sessionid):
        # TODO
        return '/tmp/session.test'

    def save(self):
        fn = Session.getSessionFileName(self.getSessionId())
        f = open(fn,'wb')
        pickle.dump(self, f)
        f.close()

    def getSessionId(self):
        return self.sessionid

    def setFinished(self):
        self.finished=True
        self.save()

    def isFinished(self):
        return self.finished

    def setRouterId(self,router):
        self.routerid=routerid
        self.save()

    def getRouterId(self):
        return self.routerid

    def setCommandId(self,command):
        self.commandid = commandid
        self.save()

    def getCommandId(self):
        return self.commandid

    def cleanParameters(self):
        self.parameters = None
        self.save()

    def addParameter(self,parameter):
        if(not self.parameters):
            self.parameters = []
        self.parameters.append(parameter)
        self.save()

    def getParameters(self):
        return self.parameters

    def setResult(self,result):
        self.result = result
        self.save()

    def getResult(self):
        return self.result

    def appendResult(self,result_fragment):
        self.result = self.result + result_fragment
        self.save()

    def getRouter(self):
        if(self.getRouterId()!=None):
            return config.routers[self.getRouterId()]
        else:
            return None

    def getCommand(self):
        if(self.getRouterId()!=None)and(self.getCommandId()!=None):
            return self.getRouter().listCommands()[self.getCommandId()]
        else:
            return None

class ULGCron:
    def __init__(self):
        pass

    def run(self):
        pass

class ULGCgi:
    def __init__(self):
        self.loader=TemplateLoader(
            os.path.join(os.path.dirname(__file__), defaults.template_dir),
            auto_reload=True
            )

    def rescanRouters(self):
        for r in config.routers:
            r.rescanHook()

    def increaseUsage(self):
        # TODO
        return True

    def decreaseUsage(self):
        # TODO
        pass

    def stopSessionOverlimit(self,session):
        session.setResult(defaults.STRING_SESSION_OVERLIMIT)
        session.setFinished()

    def loadSession(self,sessionid):
        if(sessionid == None):
            return None

        fn = Session.getSessionFileName(sessionid)

        if(os.path.isfile(fn)):
            f = open(fn, 'rb')
            s = pickle.load(f)
            f.close()
            return s
        else:
            return None

    def HTTPRedirect(self,url):
        # TODO
        return """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>Redirect!</title>
<meta http-equiv="REFRESH" content="0;url=%s">
</head>
<body>
</body>
</html>""" % url

    def getURL(self,action):
        # TODO
        return os.path.basename(__file__) + ("?action=%s" % action)

    def runCommand(self,session):
        # try to increase usage counter
        if(self.increaseUsage()):
            # start new thread if needed
            if(defaults.always_start_thread or session.getRouter().getForkNeeded()):

                # define trivial thread function
                def commandThreadBody(session,decreaseUsageMethod):
                    time.sleep(10)
                    session.setResult(session.getRouter().runCommand(session.getCommand(),session.getParameters()))
                    session.setFinished()
                    decreaseUsageMethod()

                # fork a daemon process (fork two time to decouple with parent)
                sys.stdout.flush()
                child_pid = os.fork()
                if(child_pid == 0):
                    # detach process
                    devnull = open(os.devnull,'w')
                    os.dup2(devnull.fileno(),sys.stdout.fileno())
                    os.dup2(devnull.fileno(),sys.stderr.fileno())

                    # run the command
                    commandThreadBody(session,self.decreaseUsage)

                    # exit the child
                    sys.exit(0)

            else:
                # directly run the selected action
                commandThreadBody(session,self.decreaseUsage)

        else:
            # stop and report no-op
            self.stopSessionOverlimit(session)


    def renderULGIndex(self,routerid=0,commandid=0,sessionid=None):
        tmplate = self.loader.load(defaults.index_template_file)

        # rescan routers - is it a good place for rescan?
        self.rescanRouters()

        return tmplate.generate(defaults=defaults,
                                routers=config.routers,
                                default_routerid=routerid,
                                default_commandid=commandid,
                                default_sessionid=sessionid
                                ).render('html', doctype='html')


    def renderULGAction(self,routerid=0,commandid=0,sessionid=None,**moreparams):
        routerid=int(routerid)
        commandid=int(commandid)

        # create and register session
        session = Session(sessionid=sessionid,routerid=routerid,commandid=commandid)
    
        # extract parameters
        session.cleanParameters()
        for pidx,ps in enumerate(session.getCommand().getParamSpecs()):
            if('param'+str(pidx) in moreparams.keys()):
                session.addParameter(moreparams['param'+str(pidx)])
            else:
                session.addParameter(ps.getDefault())

        # run the command (possibly in a separate thread)
        self.runCommand(session)

        # redirect to the session display
        return self.HTTPRedirect(self.getURL('display') + ('&sessionid=%s' % session.getSessionId()))


    def renderULGResult(self,sessionid=None):
        if(sessionid==None):
            return self.HTTPRedirect(self.getURL('error'))

        session = self.loadSession(sessionid)
        if(session == None):
            return self.HTTPRedirect(self.getURL('error'))

        if(session.isFinished()):
            refresh=None
        else:
            refresh = defaults.refresh_interval

        # rescan routers - is it a good place for this?
        self.rescanRouters()

        tmplate = self.loader.load(defaults.index_template_file)
        return tmplate.generate(defaults=defaults,
                                routers=config.routers,
                                default_routerid=session.getRouterId(),
                                default_commandid=session.getCommandId(),
                                default_sessionid=sessionid,
                                result=Markup(session.getResult()),
                                refresh=refresh
                                ).render('html', doctype='html')

    def renderULGError(self,sessionid=None,**params):
        tmplate = self.loader.load(defaults.index_template_file)

        session = self.loadSession(sessionid)

        result_text = defaults.STRING_ARBITRARY_ERROR

        session = self.loadSession(sessionid)
        if(session!=None):
            result_text=self.sessions[sessionid].getResult()

        return tmplate.generate(defaults=defaults,
                                routers=config.routers,
                                default_routerid=0,
                                default_commandid=0,
                                default_sessionid=None,
                                result=Markup(result_text),
                                refresh=0
                                ).render('html', doctype='html')

    def renderULGDebug(self,**params):
        tmplate = self.loader.load(defaults.index_template_file)

        result_text = "<h1>DEBUG</h1>\n<pre>\nPARAMS:\n"
        for k in params.keys():
            result_text = result_text + str(k) + "=" + str(params[k]) + "\n"
        result_test = result_text + "\n<pre>"

        return tmplate.generate(defaults=defaults,
                                routers=config.routers,
                                default_routerid=0,
                                default_commandid=0,
                                default_sessionid=None,
                                result=Markup(result_text),
                                refresh=0
                                ).render('html', doctype='html')

    def index(self, **params):
        if('sessionid' in params.keys()):
            print self.renderULGIndex(sessionid=params['sessionid'])
        else:
            print self.renderULGIndex()

    def runcommand(self,routerid=0,commandid=0,sessionid=None,**params):
        print self.renderULGAction(routerid,commandid,sessionid,**params)

    def display(self,sessionid=None,**params):
        print self.renderULGResult(sessionid)

    def error(self,sessionid=None,**params):
        print self.renderULGError(sessionid,**params)

    def debug(self,**params):
        print self.renderULGDebug(**params)

# main

if __name__=="__main__":
    form = cgi.FieldStorage()
    handler = ULGCgi()

    print "Content-Type: text/html\n"

    action = form.getvalue('action',None)
    params = dict([(k,form.getvalue(k)) for k in form.keys() if k != 'action'])
    
    if(action):
        if(action == 'index'):
            handler.index(**params)
        if(action == 'runcommand'):
            handler.runcommand(**params)
        if(action == 'display'):
            handler.display(**params)
        if(action == 'error'):
            handler.display(**params)
        if(action == 'debug'):
            handler.debug(**params)

    else:
        handler.index(**params)
