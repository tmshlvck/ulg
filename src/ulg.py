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
from genshi.template import TemplateLoader
from genshi.core import Markup
import cgi
import cgitb; cgitb.enable()
import pickle
import re
import fcntl
import traceback
import urllib
import md5
import time
import random

import config
import defaults

import ulgmodel
import whois

IPV4_ANNOTATE_REGEXP = '([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2})?)'
ipv4_annotate_regexp = re.compile(IPV4_ANNOTATE_REGEXP)

IPV6_ANNOTATE_REGEXP = '(([0-9a-fA-F]{1,4}:|:){2,7}([0-9a-fA-F]{1,4}|:)(/[0-9]{1,2})?)'
ipv6_annotate_regexp = re.compile(IPV6_ANNOTATE_REGEXP)

### CGI output handler

class Session(object):
    def __init__(self,sessionid=None,routerid=None,commandid=None,parameters=[],result=None,finished=False,error=None,resrange=None,copy=None):
        if(copy):
            self.sessionid=copy.sessionid
            self.routerid=copy.routerid
            self.commandid=copy.commandid
            self.parameters=copy.parameters
            self.error=copy.error
            self.finished=copy.finished
            self.range=copy.range
            self.resultlen=copy.resultlen
            self.data=copy.data

        else:
            if(sessionid == None):
                self.sessionid = self.__genSessionId__()
            else:
                self.sessionid=sessionid

            self.routerid=routerid
            self.commandid=commandid
            self.parameters=parameters
            self.error=error
            self.finished=finished
            self.range=resrange
            self.resultlen=0
            self.data=None

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
    def getSessionOutputFileName(sessionid):
        if(re.compile('^[a-zA-Z0-9]{10,128}$').match(sessionid)):
            return defaults.session_dir+'/'+'ulg-'+sessionid+'.out.session'
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
        except:
            ulgmodel.log("Saving session failed: " + traceback.format_exc())

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
        fn = Session.getSessionOutputFileName(self.sessionid)

        f = open(fn, 'w')
        f.write(result)
        f.close()

    def getResult(self):
        try:
            fn = Session.getSessionOutputFileName(self.sessionid)

            if(os.path.isfile(fn)):
                f = open(fn, 'r')
                result = f.read()
                f.close()
                return result
            else:
                return None
        except:
            return None

    def getDecoratedResult(self,decorator_helper,resrange=0,finished=False):
        if(self.getError()):
            # TODO
            return decorator_helper.pre(self.getResult())
        else:
            dr = self.getCommand().decorateResult(self,decorator_helper)

            if(dr):
                self.resultlines = dr[1]
                return dr[0]
            else:
                self.resultlines = 0
                return ''

    def appendResult(self,result_fragment):
        fn = Session.getSessionOutputFileName(self.sessionid)

        f = open(fn, 'a')
        f.write(result_fragment)
        f.close()

    def clearResult(self):
        try:
            fn = Session.getSessionOutputFileName(self.sessionid)

            if(os.path.isfile(fn)):
                f=open(fn,'w')
                f.close()

            self.resultlines = 0
        except:
            pass

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

    def getError(self):
        return self.error

    def setError(self,error=None):
        self.error=error
        self.save()

    def getRange(self):
        return self.range

    def setRange(self,resrange):
        self.range=resrange
        self.save()

    def showRange(self):
        return self.getCommand().showRange()

    def getMaxRange(self):
        return self.resultlines

    def getData(self):
        return self.data

    def setData(self,data):
        self.data = data
        self.save()


class DecoratorHelper:
    def __init__(self):
        pass

    def getScriptURL(self):
        return os.path.basename(__file__)

    def getURL(self,action,parameters={}):
        url=self.getScriptURL() + ("?action=%s" % urllib.quote(action))
        for k in parameters.keys():
            url = url + '&' + k + '=' + urllib.quote(parameters[k])
        return url

    def getIndexURL(self):
        return self.getURL('index')

    def getRuncommandURL(self,parameters={}):
        return self.getURL('runcommand',parameters)

    def getDisplayURL(self,sessionid,resrange=None):
        if(resrange):
            return self.getURL('display',{'sessionid':sessionid,'resrange':resrange})
        else:
            return self.getURL('display',{'sessionid':sessionid})

    def getDebugURL(self,parameters={}):
        return self.getURL('debug',parameters)

    def getErrorURL(self,parameters={}):
        return self.getURL('error',parameters)

    def getSpecialContentURL(self,sessionid,parameters={}):
        return self.getURL('getfile',dict({'sessionid':sessionid},**parameters))

    def getWhoisURL(self,key,objtype=None):
        if(objtype):
            return self.getURL('whois',dict({'key':key,'objtype':objtype}))
        else:
            return self.getURL('whois',dict({'key':key}))

    def getRouterID(self,router):
        for ridx,r in enumerate(config.routers):
            if(r == router):
                return ridx

        return 0

    def getCommandID(self,router,command):
        for cidx,c in enumerate(router.listCommands()):
            if(c == command):
                return cidx

        return 0

    def pre(self,text):
        return ('<pre>%s</pre>' % text)

    def ahref(self,url,text):
        return ('<a href=%s>%s</a>' % (str(url),str(text)))

    def copy_session(self,session):
        return Session(copy=session)

    def img(self,url,alternative_text=None):
        if(alternative_text):
            return ('<img src="%s" alt="%s">' % (url,alternative_text))
        else:
            return ('<img src="%s">' % url)

    def mwin(self,url,label=None):
        if(label == None):
            label = url
        return """<span style="cursor: pointer" onclick="TINY.box.show({iframe:'%s',boxid:'frameless',fixed:false,width:750,height:450,closejs:function(){closeJS()}})"><u>%s</u></span>""" % (url,label)

    def decorateASN(self,asn,prefix="AS"):
        asn = re.sub('[Aa][Ss][Nn]?([0-9]+)','\\1',asn)
        return self.mwin(self.getWhoisURL('AS'+str(asn),'AS'),prefix+str(asn))

    def decoratePrefix(self,ip):
        return self.mwin(self.getWhoisURL(ip,'IP'),ip)

    def annotatePrefixes4(self,line):
        s=0
        r=''
        for m in ipv4_annotate_regexp.finditer(line):
            r = r + line[s:m.start()]
            r = r + self.decoratePrefix(line[m.start():m.end()])
            s = m.end()
        return r + line[s:]

    def annotateIPs4(self,line):
        s=0
        r=''
        for m in ipv4_annotate_regexp.finditer(line):
            r = r + line[s:m.start()]
            r = r + self.decoratePrefix(line[m.start():m.end()])
            s = m.end()
        return r + line[s:]

    def annotatePrefixes6(self,line):
        s=0
        r=''
        for m in ipv6_annotate_regexp.finditer(line):
            r = r + line[s:m.start()]
            r = r + self.decoratePrefix(line[m.start():m.end()])
            s = m.end()
        return r + line[s:]

    def annotateIPs6(self,line):
        s=0
        r=''
        for m in ipv6_annotate_regexp.finditer(line):
            r = r + line[s:m.start()]
            r = r + self.decoratePrefix(line[m.start():m.end()])
            s = m.end()
        return r + line[s:]

    def annotatePrefixes(self,line):
#        return self.annotatePrefixes4(line)
        return self.annotatePrefixes6(self.annotatePrefixes4(line))

    def annotateIPs(self,line):
#        return self.annotateIPs4(line)
        return self.annotateIPs6(self.annotatePrefixes4(line))


class ULGCgi:
    def __init__(self):
        self.loader=TemplateLoader(
            os.path.join(os.path.dirname(__file__), defaults.template_dir),
            auto_reload=True
            )

        self.decorator_helper = DecoratorHelper()


    def print_text_html(self):
        print "Content-Type: text/html\n"


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
        except (IOError,ValueError) as e:
            ulgmodel.log("Locking mechanism failure: "+str(e))
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
            ulgmodel.log("Locking mechanism update failure: "+str(e))
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
            ulgmodel.log("Locking mechanism failure: "+str(e))
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
            ulgmodel.log("Locking mechanism update failure: "+str(e))
            pass

    def stopSessionOverlimit(self,session):
        session.setResult(defaults.STRING_SESSION_OVERLIMIT)
        session.setFinished()

    def getRefreshInterval(self,datalength=None):
        if(datalength):
            return (datalength/(1024*100))*defaults.refresh_interval + defaults.refresh_interval
        else:
            return defaults.refresh_interval

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
        class FakeSessionFile(object):
            def __init__(self,session):
                self.session = session

            def write(self,string):
                self.session.appendResult(string)

        # define trivial thread function
        def commandThreadBody(session,decreaseUsageMethod):
            ulgmodel.debug("Running command: "+session.getCommand().getName())
            try:
                session.getRouter().runAsyncCommand(session.getCommand(),session.getParameters(),FakeSessionFile(session))
                session.getCommand().finishHook(session)
            except Exception as e:
                ulgmodel.log("ERROR: Exception occured while running a command:" + traceback.format_exc())
                session.setResult("ERROR in commandThreadBody:\n"+traceback.format_exc())
            finally:
                ulgmodel.debug("Command finished: "+session.getCommand().getName())
                session.setFinished()
                decreaseUsageMethod()

        # try to increase usage counter
        if(self.increaseUsage()):
            # start new thread if needed
            if(defaults.always_start_thread or session.getRouter().getForkNeeded()):
                # fork a daemon process (fork two times to decouple with parent)
                sys.stdout.flush()
                child_pid = os.fork()
                if(child_pid == 0):
                    # detach process
                    devnull = open(os.devnull,'w')
                    os.dup2(devnull.fileno(),sys.stdout.fileno())
                    os.dup2(devnull.fileno(),sys.stderr.fileno())

                    # run the command
                    ulgmodel.debug("Running in a forked process...")
                    commandThreadBody(session,self.decreaseUsage)
                    ulgmodel.debug("Forked process finished...")

                    # exit the child
                    sys.exit(0)
                else:
                    ulgmodel.debug("Forked a new process PID: "+str(child_pid))

            else:
                # directly run the selected action, DEPRECATED
                commandThreadBody(session,self.decreaseUsage)
        else:
            # stop and report no-op
            self.stopSessionOverlimit(session)


    def renderULGIndex(self,routerid=0,commandid=0,sessionid=None):
        template = self.loader.load(defaults.index_template_file)

        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=routerid,
                                 default_commandid=commandid,
                                 default_sessionid=sessionid,
                                 getFormURL=self.decorator_helper.getRuncommandURL
                                 ).render('html', doctype='html')


    def renderULGAction(self,routerid=0,commandid=0,sessionid=None,**moreparams):
        routerid=int(routerid)
        commandid=int(commandid)

        # create and register session
        session = Session(sessionid=sessionid,routerid=routerid,commandid=commandid)
        session.clearResult()
    
        # extract parameters
        session.cleanParameters()
        for pidx,ps in enumerate(session.getCommand().getParamSpecs()):
            if('param'+str(pidx) in moreparams.keys()):
                session.addParameter(str(moreparams['param'+str(pidx)]))
            else:
                session.addParameter(ps.getDefault())

        # run the command (possibly in a separate process)
        self.runCommand(session)

        # redirect to the session display
        return self.HTTPRedirect(self.decorator_helper.getDisplayURL(session.getSessionId()))


    def renderULGResult(self,sessionid=None,resrange=0):
        def getRangeStepURLs(session,decorator_helper):
            if(not session.showRange()):
                return None

            cur_range = session.getRange()
            max_range = session.getMaxRange()

            if(max_range < defaults.range_step):
                return None

            res = []
            if((cur_range - defaults.range_step * 100) >= 0):
                res.append(('<<',decorator_helper.getDisplayURL(session.getSessionId(),str(cur_range - defaults.range_step * 100))))
            if((cur_range - defaults.range_step * 10) >= 0):
                res.append(('<',decorator_helper.getDisplayURL(session.getSessionId(),str(cur_range - defaults.range_step * 10))))

            boundary_size = 8
            leftb = max(0,cur_range - boundary_size*defaults.range_step)
            rightb = min(leftb + 2*boundary_size*defaults.range_step,max_range)

            for rb in range(leftb,rightb,defaults.range_step):
                if(rb != cur_range):
                    res.append((str(rb),decorator_helper.getDisplayURL(session.getSessionId(),str(rb))))
                else:
                    res.append((str(rb),None))

            if((cur_range + defaults.range_step * 10) < max_range):
                res.append(('>',decorator_helper.getDisplayURL(session.getSessionId(),str(cur_range + defaults.range_step * 10))))
            if((cur_range + defaults.range_step * 100) < max_range):
                res.append(('>>',decorator_helper.getDisplayURL(session.getSessionId(),str(cur_range + defaults.range_step * 100))))

            return res

        if(sessionid==None):
            return self.HTTPRedirect(self.decorator_helper.getErrorURL())

        session = Session.load(sessionid)
        if(session == None):
            return self.HTTPRedirect(self.decorator_helper.getErrorURL())

        session.setRange(int(resrange))

        result_text = session.getDecoratedResult(self.decorator_helper,session.getRange(),session.isFinished())

        if(session.isFinished()):
            refresh=None
        else:
            if(result_text):
                refresh = self.getRefreshInterval(len(result_text))
            else:
                refresh = self.getRefreshInterval()

        template = self.loader.load(defaults.index_template_file)
        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=session.getRouterId(),
                                 default_commandid=session.getCommandId(),
                                 default_params=session.getParameters(),
                                 default_sessionid=sessionid,
                                 result=Markup(result_text) if(result_text) else None,
                                 refresh=refresh,
                                 getFormURL=self.decorator_helper.getRuncommandURL,
                                 resrange=str(session.getRange()),
                                 resrangeb=getRangeStepURLs(session,self.decorator_helper),
                                 ).render('html', doctype='html')

    def renderULGError(self,sessionid=None,**params):
        template = self.loader.load(defaults.index_template_file)

        result_text = defaults.STRING_ARBITRARY_ERROR

        session = Session.load(sessionid)
        if(session!=None):
            result_text=self.decorator_helper.pre(self.sessions[sessionid].getError())

        return template.generate(defaults=defaults,
                                 routers=config.routers,
                                 default_routerid=0,
                                 default_commandid=0,
                                 default_sessionid=None,
                                 result=Markup(result_text) if(result_text) else None,
                                 refresh=0,
                                 getFormURL=self.decorator_helper.getRuncommandURL
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
                                 result=Markup(result_text) if(result_text) else None,
                                 refresh=0,
                                 getFormURL=self.decorator_helper.getRuncommandURL()
                                 ).render('html', doctype='html')


    def getULGSpecialContent(self,sessionid,**params):
        if(sessionid==None):
            return self.HTTPRedirect(self.decorator_helper.getErrorURL())

        session = Session.load(sessionid)
        if(session == None):
            return self.HTTPRedirect(self.decorator_helper.getErrorURL())

        # speciality here: the function is responsible for printing the output itself
        session.getCommand().getSpecialContent(session,**params)

    def runULGWhois(self,key,objtype):
        url=None
        urlc=None
        if(objtype == 'IP'):
            url=defaults.getIPPrefixURL(key)
            urlc=defaults.STRING_DETAILS+' '+str(key)
        elif(objtype == 'AS'):
            url=defaults.getASNURL(key)
            urlc=defaults.STRING_DETAILS+' '+key

        m = re.match('^\s*([^/]+)/[0-9]+\s*$',key)
        if(m):
            key = m.group(1)

        template = self.loader.load(defaults.whois_template_file)

        res = whois.lookup(key)
        return template.generate(result=Markup(res),
                                 url=url,
                                 url_caption=urlc,
                                 ).render('html', doctype='html')


    def index(self, **params):
        self.print_text_html()
        if('sessionid' in params.keys()):
            print self.renderULGIndex(sessionid=params['sessionid'])
        else:
            print self.renderULGIndex()

    def runcommand(self,routerid=0,commandid=0,sessionid=None,**params):
        self.print_text_html()
        print self.renderULGAction(routerid,commandid,sessionid,**params)

    def display(self,sessionid=None,**params):
        self.print_text_html()
        print self.renderULGResult(sessionid,**params)

    def getfile(self,sessionid=None,**params):
        self.getULGSpecialContent(sessionid,**params)

    def whois(self,key,objtype=None):
        self.print_text_html()
        if(key):
            print self.runULGWhois(key,objtype)
        else:
            print self.HTTPRedirect(self.decorator_helper.getErrorURL())

    def error(self,sessionid=None,**params):
        self.print_text_html()
        print self.renderULGError(sessionid,**params)

    def debug(self,**params):
        self.print_text_html()
        print self.renderULGDebug(**params)

# main

if __name__=="__main__":
    try:
        form = cgi.FieldStorage()
        handler = ULGCgi()

        action = form.getvalue('action',None)
        params = dict([(k,form.getvalue(k)) for k in form.keys() if k != 'action'])
    
        if(action):
            if(action == 'index'):
                handler.index(**params)
            elif(action == 'runcommand'):
                handler.runcommand(**params)
            elif(action == 'display'):
                handler.display(**params)
            elif(action == 'getfile'):
                handler.getfile(**params)
            elif(action == 'whois'):
                handler.whois(**params)
            elif(action == 'error'):
                handler.error(**params)
            elif(action == 'debug'):
                handler.debug(**params)
            else:
                ulgmodel.log('ERROR: Unknown action called: '+action+'\n')
                handler.display(**params)

        else:
            handler.index(**params)
    except Exception as e:
        ulgmodel.log("ERROR in CGI: "+traceback.format_exc())
