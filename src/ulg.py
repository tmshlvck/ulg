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
from genshi.template import TemplateLoader
from genshi.core import Markup
import os
import pexpect
import socket
import re

import defaults

STRING_ANY='any'
STRING_PARAMETER='Parameter'
STRING_COMMAND='Command'
STRING_ERROR='Error encountered while preparing or running command'
STRING_BAD_PARAMS='Verification of command or parameters failed.'

STRING_EXPECT_SSH_NEWKEY='Are you sure you want to continue connecting'
STRING_EXPECT_PASSWORD='(P|p)assword:'


class TextParameter(object):
    def __init__(self,pattern='.*',name=STRING_PARAMETER,default=''):
        self.name=name
        self.pattern=pattern
        self.default=default

    def getType(self):
        return 'text'

    def getName(self):
        return self.name

    def getDefault(self):
        return self.default

    def checkInput(self,input):
        if(re.compile(self.pattern).match(input)):
            return True
        else:
            return False

    def normalizeInput(self,input):
        if(self.checkInput(input)[0]):
            return input
        else:
            raise Exception("Invalid input encountered: Check did not passed.")

class SelectionParameter(TextParameter):
    def __init__(self,option_names=[],option_values=[],name=STRING_PARAMETER,default=0):
        self.option_names=option_names

    def getType(self):
        return 'select'

    def setOptions(self,option_names,option_values):
        self.option_names=option_names
        self.option_values=option_values

    def setOptionsFromTuples(self,tuples):
        # TODO
        pass

    def getOptions(self):
        return (self.option_names,self.option_values)

    def getOptionTuples(self):
        # TODO
        pass

    def checkInput(self,input):
        index=0
        try:
            index=int(input)
        except:
            return False
        return True

    def normalizeInput(self,input):
        if(self.checkInput(input)):
            return option_values[int(input)]
        else:
            raise Exception("Invalid input encountered: Check did not passed.")        

class TextCommand(object):
    def __init__(self,command,param_specs=[],name=None):
        self.command=command
        self.param_specs=param_specs

        self.loader = TemplateLoader(
            os.path.join(os.path.dirname(__file__), defaults.template_dir),
            auto_reload=True
            )

        if(name==None):
            self.name=command

    def getCommand(self,parameters=None):
        if(self.checkParamsInput(parameters)):
            c = self.command

            for p in parameters:
                c = c + ' ' + p

            return c
        else:
            return None

    def getParamSpecs(self):
        return self.param_specs

    def getName(self):
        return self.name

    def checkParamsInput(self,input):
        if(((input == None)or(self.getParamSpecs()==None))and(self.getParamSpecs()!=input)):
            return False

        if(len(input)!=len(self.getParamSpecs())):
            return False

        for pidx,p in enumerate(self.getParamSpecs()):
            if not p.checkInput(input[pidx]):
                return False

        return True

    def rescanHook(self):
        pass

    def decorateResult(self,result,router=None):
        return "<pre>\n%s\n</pre>" % result
    
class AnyCommand(TextCommand):
    def __init__(self):
        self.command=''
        self.parameter = TextParameter('.+', name=STRING_COMMAND)
        self.name=STRING_ANY

    def getCommand(self,parameters=None):
        c = ''
        for p in parameters:
            if(c==''):
                c = p
            else:
                c = c + ' ' + p

        return c

class Router(object):
    def __init__(self):
        self.setCommands({})
        self.setName('')

    def setName(self,name):
        self.name=name

    def getName(self):
        return self.name

    def setCommands(self, commands):
        self.commands=commands

    def listCommands(self):
        return self.commands

    def rescanHook(self):
        for c in self.listCommands():
            c.rescanHook()

    def returnError(self,error=None):
        r = '<em>'+STRING_ERROR
        r = r + ': '+error+'</em>' if error else r+'.</em>'
        return r

    def runCommand(self,command,parameters):
        c = command.getCommand(self.normalizeParameters(parameters))

        if(c == None):
            return self.returnError(STRING_BAD_PARAMS)

        r = ''
        if(defaults.debug):
            r = "<h3>DEBUG</h3><pre>Router.runCommand():\ncommand_name="+command.getName()+'\n'
            if(parameters != None):
                for pidx,p in enumerate(parameters):
                    r = r + " param"+str(pidx)+"="+str(p)+"\n"
            r = r + "complete command="+c+"\n" + \
                "</pre><hr>"

        r = r + command.decorateResult(self.runRawCommand(c),self)
        return r

    def runRawCommand(self,command):
        """ Abstract method. """
        raise Exception("runRawCommand() method not supported for the abstract class Router. Inherit from the class and implement the method.")

    def normalizeParameters(self,parameters):
        return [] if parameters == None else [command.getParameterSpecs()[pidx].normalizeInput(p) for pidx,p in enumerate(parameters)]

    def getForkNeeded(self):
        return False

class RemoteRouter(Router):
    def getHost(self):
        return self.host

    def setHost(self,host):
        self.host = host

    def getPort(self):
        return self.port

    def setPort(self,port):
        self.port = port

    def getUser(self):
        return self.user

    def setUser(self,user):
        self.user = user

    def setPassword(self, password):
        self.password = password

class LocalRouter(Router):
    pass

class CiscoRouter(RemoteRouter):
    DefaultCommands = [TextCommand('show version'),
                       TextCommand('show ip bgp', [TextParameter('.*')]),
                       TextCommand('show bgp ipv4 uni sum'),
                       TextCommand('show bgp ipv6 uni sum'),
                       TextCommand('show bgp ipv4 uni neighbor',[TextParameter('[0-9]{1-3}\.[0-9]{1-3}\.[0-9]{1-3}\.[0-9]{1-3}')]),
                       TextCommand('show bgp ipv4 uni neighbor',[TextParameter('[0-9a-fA-F:]+)]')]),
                       ]
    STRING_SHELL_PROMPT = '>'

    def __init__(self, host, user, password, port=22, commands=None):
        self.setHost(host)
        self.setPort(port)
        self.setUser(user)
        self.setPassword(password)
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(CiscoRouter.DefaultCommands)
        self.setName(host)

    def getForkNeeded(self):
        return True

    def runRawCommand(self,command):
        return self._runTextCommand(command)

    def _runTextCommand(self,command):
        # connect
        p=pexpect.spawn(defaults.bin_ssh+' -p'+str(self.getPort())+' '+str(self.getUser())+'@'+self.getHost())

        # handle ssh
        i=p.expect([STRING_EXPECT_SSH_NEWKEY,STRING_EXPECT_PASSWORD,pexpect.EOF])
        if(i==0):
            p.sendline('yes')
            i=p.expect([STRING_EXPECT_SSH_NEWKEY,STRING_EXPECT_PASSWORD,pexpect.EOF])

        if(i==0):
            raise Exception("pexpect session failed: Can not save SSH key.")
        elif(i==1):
            p.sendline(self.password)
        elif(i==2):
            raise Exception("pexpect session failed: Connection timeout or SSH error.")
        else:
            raise Exception("pexpect session failed: SSH error.")

        # check shell and preset terminal
        i=p.expect([CiscoRouter.STRING_SHELL_PROMPT,pexpect.EOF])
        if(i==0):
            p.sendline('terminal length 0')
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")

        i=p.expect([CiscoRouter.STRING_SHELL_PROMPT,pexpect.EOF])
        if(i==0):
            p.sendline('terminal width 0')
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")

        i=p.expect([CiscoRouter.STRING_SHELL_PROMPT,pexpect.EOF])
        if(i==0):
            p.sendline(command)
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")
        
        p.expect(['\n[^\n]*'+CiscoRouter.STRING_SHELL_PROMPT])
        return p.before


class BirdRouterLocal(LocalRouter):
    DefaultCommands = [TextCommand('show protocols', [TextParameter('.*')])]

    def __init__(self,sock=defaults.default_bird_sock,commands=None):
        super(self.__class__,self).__init__()
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(BirdRouterLocal.DefaultCommands)
        self.sock = sock
        self.setName('localhost')

    def runRawCommand(self,command):
        # open socket to BIRD
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.sock)

        # cretate FD for the socket
        sf=s.makefile()

        # send the command string
        s.send(command)

        # read and capture lines until the output delimiter string is hit
        result=''
        for l in sf:
            if(re.compile('^0000').match(l)):
                result=result+"BREAK\n"
                break
            result=result+l

        # close the socket and return captured result
        s.close()
        return result
