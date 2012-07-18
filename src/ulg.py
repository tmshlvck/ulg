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
import re
import fcntl

import config
import defaults

import ulgmodel

### CGI output handler

class Session(object):
    def __init__(self,sessionid=None,routerid=None,commandid=None,parameters=[],result=None,finished=False):
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
        if(re.compile('^[a-zA-Z0-9]{10,128}$').match(sessionid)):
            return defaults.session_dir+'/'+'ulg-'+sessionid+'.session'
        else:
            raise Exception('Invalid session id passed. Value was: '+sessionid)

    @staticmethod
    def load(sessionid):
        if(sessionid == None):
            return None

        try:
            fn = Session.getSessionFileName(sessionid)

            if(os.path.isfile(fn)):
                f = open(fn, 'rb')
                s = pickle.load(f)
                f.close()
                return s
            else:
                return None
            
        except Exception:
            return None

    def save(self):
        try:
            fn = Session.getSessionFileName(self.getSessionId())
            f = open(fn,'wb')
            pickle.dump(self, f)
            f.close()
        finally:
            # TODO log("Saving session failed: " + traceback.format_exc())
            pass

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
        self.parameters = []
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

class Decorator:
    def __init__(self):
        pass

    def getScriptURL(self):
        return os.path.basename(__file__)

    def getURL(self,action,parameters={}):
        url=self.getScriptURL() + ("?action=%s" % action)
        for k in parameters.keys():
            url = url + '&' + k + '=' + parameters[k]
        return url

    def getIndexURL(self):
        return self.getURL('index')

    def getRuncommandURL(self,parameters={}):
        return self.getURL('runcommand',parameters)

    def getDisplayURL(self,sessionid):
        return self.getURL('display',{'sessionid':sessionid})

    def getDebugURL(self,parameters={}):
        return self.getURL('debug',parameters)

    def getErrorURL(self,parameters={}):
        return self.getURL('error',parameters)

    def getRouterID(self,router):
        # TODO
        return 0

    def getCommandID(self,router,command):
        # TODO
        return 0

class ULGCgi:
    def __init__(self):
        self.loader=TemplateLoader(
            os.path.join(os.path.dirname(__file__), defaults.template_dir),
            auto_reload=True
            )

        self.decorator = Decorator()

    def rescanRouters(self):
        for r in config.routers:
            r.rescanHook()

    def increaseUsage(self):
        u = 0
        try:
            # Open files
            if(os.path.isfile(defaults.usage_counter_file)):
                lf = open(defaults.usage_counter_file,'r+')
                u = int(lf.readline())
            else:
                lf = open(defaults.usage_counter_file,'w')

            # Acquire lock
            fcntl.lockf(lf, fcntl.LOCK_EX)
        except IOError,ValueError:
            # TODO: log("Locking mechanism failure: "+str(e))
            return False

        try:
            if(u < defaults.usage_limit):
                # write a new value and release lock
                lf.seek(0)
                lf.write(str(u+1)+'\n')
                lf.close()
                return True
            else:
                # release lock
                lf.close()
                return False
        except IOError as e:
            # TODO: log("Locking mechanism update failure: "+str(e))
            return False

    def decreaseUsage(self):
        u = 1
        try:
            # Open files
            if(os.path.isfile(defaults.usage_counter_file)):
                lf = open(defaults.usage_counter_file,'r+')
                u = int(lf.readline())
            else:
                lf = open(defaults.usage_counter_file,'w')

            # Acquire lock
            fcntl.lockf(lf, fcntl.LOCK_EX)
        except IOError,ValueError:
            # TODO: log("Locking mechanism failure: "+str(e))
            return False

        try:
            if(u>0):
                # write a new value and release lock
                lf.seek(0)
                lf.write(str(u-1)+'\n')
                lf.close()
                return
            else:
                # release lock
                lf.close()
                return
        except IOError as e:
            # TODO: log("Locking mechanism update failure: "+str(e))
            pass

    def stopSessionOverlimit(self,session):
        session.setResult(defaults.STRING_SESSION_OVERLIMIT)
        session.setFinished()

    def HTTPRedirect(self,url):
        return """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>Redirect!</title>
<meta http-equiv="REFRESH" content="0;url=%s">
</head>
<body>
</body>
</html>""" % url

    def runCommand(self,session):
        # try to increase usage counter
        if(self.increaseUsage()):
            # start new thread if needed
            if(defaults.always_start_thread or session.getRouter().getForkNeeded()):

                # define trivial thread function
                def commandThreadBody(session,decreaseUsageMethod):
                    try:
                        session.setResult(session.getRouter().runCommand(session.getCommand(),session.getParameters(),self.decorator))
                        session.setFinished()
                    except Exception as e:
                        # TODO: log("Exception occured while running a command")
                        pass
                    finally:
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
        template = self.loader.load(defaults.index_template_file)

        # rescan routers - is it a good place for rescan?
        self.rescanRouters()

        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=routerid,
                                 default_commandid=commandid,
                                 default_sessionid=sessionid,
                                 getFormURL=self.decorator.getRuncommandURL
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
        return self.HTTPRedirect(self.decorator.getDisplayURL(session.getSessionId()))


    def renderULGResult(self,sessionid=None):
        if(sessionid==None):
            return self.HTTPRedirect(self.decorator.getErrorURL())

        session = Session.load(sessionid)
        if(session == None):
            return self.HTTPRedirect(self.decorator.getErrorURL())

        if(session.isFinished()):
            refresh=None
        else:
            refresh = defaults.refresh_interval

        # rescan routers - is it a good place for this?
        self.rescanRouters()

        template = self.loader.load(defaults.index_template_file)
        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=session.getRouterId(),
                                 default_commandid=session.getCommandId(),
                                 default_params=session.getParameters(),
                                 default_sessionid=sessionid,
                                 result=Markup(session.getResult()),
                                 refresh=refresh,
                                 getFormURL=self.decorator.getRuncommandURL
                                 ).render('html', doctype='html')

    def renderULGError(self,sessionid=None,**params):
        template = self.loader.load(defaults.index_template_file)

        result_text = defaults.STRING_ARBITRARY_ERROR

        session = Session.load(sessionid)
        if(session!=None):
            result_text=self.sessions[sessionid].getResult()

        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=0,
                                 default_commandid=0,
                                 default_sessionid=None,
                                 result=Markup(result_text),
                                 refresh=0,
                                 getFormURL=self.decorator.getRuncommandURL
                                 ).render('html', doctype='html')
    
    def renderULGDebug(self,**params):
        template = self.loader.load(defaults.index_template_file)

        result_text = "<h1>DEBUG</h1>\n<pre>\nPARAMS:\n"
        for k in params.keys():
            result_text = result_text + str(k) + "=" + str(params[k]) + "\n"
        result_test = result_text + "\n<pre>"

        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=0,
                                 default_commandid=0,
                                 default_sessionid=None,
                                 result=Markup(result_text),
                                 refresh=0,
                                 getFormURL=self.decorator.getRuncommandURL
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
