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
import os
import re
from time import localtime, strftime
from genshi.template import TemplateLoader
from genshi.core import Markup
import pickle
import fcntl
import StringIO
import socket

import whois
import defaults


IPV4_SUBNET_REGEXP = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2}){0,1}$'
IPV4_ADDRESS_REGEXP = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
IPV6_SUBNET_REGEXP = '^[0-9a-fA-F:]+(/[0-9]{1,2}){0,1}$'
IPV6_ADDRESS_REGEXP = '^[0-9a-fA-F:]+$'

def log(*messages):
    try:
        with open(defaults.log_file, 'a') as l:
            for m in messages:
                l.write(strftime("%b %d %Y %H:%M:%S: ", localtime()) + m + "\n")
    except Exception:
        pass

def debug(message):
    if(defaults.debug):
        log('DEBUG:' + message)


def annotateAS(asn):
    return asn+' | '+whois.lookup_as_name(asn)


class PersistentStorage(object):
    def __init__(self):
        self.data = {}

    def save(self,filename=defaults.persistent_storage_file):
        # TODO: locking
        f = open(filename,'wb')
        pickle.dump(self, f)
        f.close()

    @staticmethod
    def load(filename=defaults.persistent_storage_file):
        # TODO: locking
        if(os.path.isfile(filename)):
            f = open(filename, 'rb')
            s = pickle.load(f)
            f.close()
            return s
        else:
            return PersistentStorage()

    def get(self,key):
        return self.data.get(key,None)

    def set(self,key,value):
        self.data[key] = value

    def delete(self,key):
        if(key in self.data.keys()):
            del(self.data[key])

    def getDict(self):
        return self.data

class TableDecorator(object):
    WHITE = 'white'
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'
    YELLOW = 'yellow'
    BLACK = 'black'

    def __init__(self, table, table_header, table_headline=None, before=None, after=None):
        self.table = table
        self.table_header = table_header
        self.table_headline = table_headline
        self.before = before
        self.after = after

        self.loader=TemplateLoader(
            os.path.join(os.path.dirname(__file__), defaults.template_dir),
            auto_reload=True
            )

    def decorate(self):
        def preprocessTableCell(td):
            if(isinstance(td,(list,tuple))):
                if(len(td) >= 2):
                    return (Markup(str(td[0])),Markup(str(td[1])))
                elif(len(td) == 1):
                    return (Markup(str(td[0])),Markup(TableDecorator.WHITE))
                else:
                    return ('',Markup(TableDecorator.WHITE))
            else:
                return (Markup(str(td)),Markup(TableDecorator.WHITE))

        t = [[preprocessTableCell(td) for td in tr ] for tr in self.table]

        template = self.loader.load(defaults.table_decorator_template_file)
        return template.generate(table=t,
                                 table_header=self.table_header,
                                 table_headline=Markup(self.table_headline) if self.table_headline else '',
                                 before=Markup(self.before) if self.before else '',
                                 after=Markup(self.after) if self.after else '',
                                 ).render('html')


class TextParameter(object):
    def __init__(self,pattern='.*',name=defaults.STRING_PARAMETER,default=''):
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
        if(self.checkInput(input)):
            return input
        else:
            raise Exception("Invalid input encountered: Check did not passed.")

class AddressParameter(TextParameter):
    def __init__(self,pattern=None,name=defaults.STRING_IPADDRESS,default=''):
        TextParameter.__init__(self,pattern,name,default)

    def _resolveAddress(self,input):
        try:
            return(socket.getaddrinfo(input,80,self.addrfam,0,socket.SOL_TCP)[0][4][0])
        except Exception as e:
            return None

    def checkInput(self,input):
        if(re.compile(self.pattern).match(input)):
            return True

        if(self._resolveAddress(input)):
            return True
        else:
            return False

    def normalizeInput(self,input):
        if(re.compile(self.pattern).match(input)):
            return input

        res = self._resolveAddress(input)
        if(res):
            return res
        else:
            return input

class IPv4SubnetParameter(AddressParameter):
    def __init__(self,name=defaults.STRING_IPSUBNET,default=''):
        AddressParameter.__init__(self,IPV4_SUBNET_REGEXP,name,default)
        self.addrfam=socket.AF_INET

    def _resolveAddress(self,input):
        addr = AddressParameter._resolveAddress(self,input)
        if(addr):
            return (addr)
        else:
            return None

class IPv4AddressParameter(AddressParameter):
    def __init__(self,name=defaults.STRING_IPADDRESS,default=''):
        AddressParameter.__init__(self,IPV4_ADDRESS_REGEXP,name,default)
        self.addrfam=socket.AF_INET

class IPv6SubnetParameter(AddressParameter):
    def __init__(self,name=defaults.STRING_IPSUBNET,default=''):
        AddressParameter.__init__(self,IPV6_SUBNET_REGEXP,name,default)
        self.addrfam=socket.AF_INET6

    def _resolveAddress(self,input):
        addr = AddressParameter._resolveAddress(self,input)
        if(addr):
            return (addr)
        else:
            return None

class IPv6AddressParameter(AddressParameter):
    def __init__(self,name=defaults.STRING_IPADDRESS,default=''):
        AddressParameter.__init__(self,IPV6_ADDRESS_REGEXP,name,default)
        self.addrfam=socket.AF_INET6


class SelectionParameter(TextParameter):
    def __init__(self,option_tuples=[],name=defaults.STRING_PARAMETER,default=None):
        "option_tupes=[(value,name),(value2,name2),(value3equalsname3,),...]"
        self.option_tuples = []
        self.setOptions(option_tuples)
        self.name=name
        self.default=default

    def getType(self):
        return 'select'

    def getDefault(self):
        if(self.default and (self.default in [v[0] for v in self.getOptions()])):
            return self.default
        else:
            return self.getOptions()[0]

    def setOptions(self,option_tuples):
        self.option_tuples = []
        for o in option_tuples:
            if(len(o) >= 2):
                self.option_tuples.append(tuple((o[0],o[1],)))
            elif(len(o) == 1):
                self.option_tuples.append(tuple((o[0],o[0],)))
            else:
                raise Exception("Invalid option passed in SelectionParameter configuration. Zero-sized tuple.")

    def getOptions(self):
        return self.option_tuples

    def checkInput(self,input):
        if(input and (input in [v[0] for v in self.getOptions()])):
            return True
        else:
            return False

    def normalizeInput(self,input):
        log("DEBUG: returning selection parameter input: "+str(input))
        if(self.checkInput(input)):
            return input
        else:
            raise Exception("Invalid input encountered: Check did not passed.")


class TextCommand(object):
    def __init__(self,command,param_specs=[],name=None):
        self.command=command
        self.param_specs=param_specs

        if(name==None):
            if(self.param_specs):
                self.name=command % tuple([('<'+str(c.getName())+'>') for c in self.param_specs])
            else:
                self.name=command
        else:
            self.name=name

    def getParamSpecs(self):
        return self.param_specs

    def getName(self):
        return self.name

    def checkParamsInput(self,input):
        if(((not input) and (self.getParamSpecs()))or((input) and (not self.getParamSpecs()))):
            log("Failed checking parameter count to zero, input:"+str(input)+' .')
            return False

        if(len(input)!=len(self.getParamSpecs())):
            log("Failed checking parameter count (nonzero), input: "+str(input)+' .')
            return False

        for pidx,p in enumerate(self.getParamSpecs()):
            if not p.checkInput(input[pidx]):
                log("Failed checking parameter: "+str(input[pidx]))
                return False

        return True

    def normalizeParameters(self,parameters):
        if parameters == None:
            return [] 
        else:
            return [self.getParamSpecs()[pidx].normalizeInput(p) for pidx,p in enumerate(parameters)]

    def getCommandText(self,parameters=None):
        if(self.checkParamsInput(parameters)):
            parameters_normalized = self.normalizeParameters(parameters)

            if(parameters_normalized):
                return self.command % tuple(parameters_normalized)
            else:
                return self.command

        else:
            return None

    def rescanHook(self,router):
        pass

    def decorateResult(self,session,decorator_helper=None):
        if(session.getRange() != None and self.showRange()):
            s = str.splitlines(session.getResult())
            r=''
            for sl in s[session.getRange():session.getRange()+defaults.range_step+1]:
                r += sl + "\n"
            return ("<pre>\n%s\n</pre>" % r, len(s))
        else:
            return ("<pre>\n%s\n</pre>" % session.getResult(), len(str.splitlines(session.getResult())))

    def getSpecialContent(self,session,**params):
        raise Exception("getSpecialContet() is not implemented in ulgmodel.TextCommand.")

    def showRange(self):
        return True

    def finishHook(self,session):
        pass
    
class AnyCommand(TextCommand):
    def __init__(self):
        self.command=''
        self.parameter = TextParameter('.+', name=defaults.STRING_COMMAND)
        self.name=defaults.STRING_ANY
        self.asn = 'My ASN'

    def getCommandText(self,parameters=None):
        c = ''

        parameters_normalized = self.normalizeParameters(parameters)
        if(len(parameters_normalized) == 0):
            raise Exception("Can not construct AnyCommand without valid parameter.")

        for p in parameters_normalized:
            c = c + ' ' + p

        return c

class Router(object):
    def __init__(self):
        self.setCommands([])
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
            c.rescanHook(self)

    def returnError(self,error=None):
        r = '<em>'+defaults.STRING_ERROR_COMMANDRUN
        r = r + ': '+error+'</em>' if error else r+'.</em>'
        return r

    def __prepareCommand(self,command,parameters):
        c = command.getCommandText(parameters)

        if(c == None):
            log("Bad params encountered in command "+str(command.getName())+" : "+str(parameters))
            return None

        debug("Going to run command "+c+" on router "+self.getName())
        return c

    def runSyncCommand(self,command,parameters):
        c = self.__prepareCommand(command,parameters)
        if(c):
            return self.runRawSyncCommand(c)
        else:
            return self.returnError(defaults.STRING_BAD_PARAMS)

    def runAsyncCommand(self,command,parameters,outfile):
        c = self.__prepareCommand(command,parameters)
        if(c):
            return self.runRawCommand(c,outfile)
        else:
            outfile.write(self.returnError(defaults.STRING_BAD_PARAMS))
            return

    def runRawSyncCommand(self,command):
        cr = StringIO.StringIO()
        self.runRawCommand(command,cr)
        return cr.getvalue()

    def runRawCommand(self,command,outfile):
        """ Abstract method. """
        raise Exception("runRawCommand() method not supported for the abstract class Router. Inherit from the class and implement the method.")

    def getForkNeeded(self):
        return False

    def setASN(self,asn):
        self.asn = asn

    def getASN(self):
        return self.asn

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

