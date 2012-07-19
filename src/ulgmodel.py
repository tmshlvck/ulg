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
import os
import re

import defaults


class PersistentStorgage(object):
    def __init__(self,filename=defaults.persistent_storage_file):
        self.filename = filename
        self.data = {}

    def save(self):
        f = open(self.filename,'wb')
        pickle.dump(self, f)
        f.close()

    @staticmethod
    def load(filename=defaults.persistent_storage_file):
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

    def getDict(self):
        return self.data


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

class SelectionParameter(object):
    def __init__(self,option_tuples=[],name=defaults.STRING_PARAMETER,default=0):
        "option_tupes=[(name,value),(name2,value2),(name3equalsvalue3,),...]"
        self.setOptions(option_tuples)
        self.name=name
        self.default=default

    def getType(self):
        return 'select'

    def getName(self):
        return self.name

    def getDefault(self):
        return self.default

    def setOptions(self,option_tuples):
        self.option_tuples=option_tuples

    def getOptions(self):
        return self.option_tuples

    def getOptionNames(self):
        return [o[0] for o in self.getOptions()]

    def checkInput(self,input):
        index=0
        try:
            index=int(input)
        except ValueError:
            return False

        if(index>=0 and index<len(self.getOptions())):
            return True
        else:
            return False

    def normalizeInput(self,input):
        if(self.checkInput(input)):
            if(len(self.getOptions()[int(input)])==2):
                return self.getOptions()[int(input)][1]
            else:
                return self.getOptions()[int(input)][0]
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

    def getParamSpecs(self):
        return self.param_specs

    def getName(self):
        return self.name

    def checkParamsInput(self,input):
        if(((not input) and (self.getParamSpecs()))or((input) and (not self.getParamSpecs()))):
            # TODO log/debug
            print "Failed checking parameter count to zero."
            return False

        if(len(input)!=len(self.getParamSpecs())):
            # TODO log
            print "Failed checking parameter count (nonzero)."
            return False

        for pidx,p in enumerate(self.getParamSpecs()):
            if not p.checkInput(input[pidx]):
                # TODO log
                print "Failed checking parameter: "+input[pidx]
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

    def decorateResult(self,result,router=None,decorator=None):
        return "<pre>\n%s\n</pre>" % result
    
class AnyCommand(TextCommand):
    def __init__(self):
        self.command=''
        self.parameter = TextParameter('.+', name=defaults.STRING_COMMAND)
        self.name=defaults.STRING_ANY

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
            c.rescanHook(self)

    def returnError(self,error=None):
        r = '<em>'+defaults.STRING_ERROR_COMMANDRUN
        r = r + ': '+error+'</em>' if error else r+'.</em>'
        return r

    def runCommand(self,command,parameters,decorator):
        c = command.getCommandText(parameters)

        if(c == None):
            #TODO: log("Bad params encountered in command "+str(command.getName())+" : "+str(parameters))
            return self.returnError(defaults.STRING_BAD_PARAMS)

        r = ''
        if(defaults.debug):
            r = "<h3>DEBUG</h3><pre>Router.runCommand():\ncommand_name="+command.getName()+'\n'
            if(parameters != None):
                for pidx,p in enumerate(parameters):
                    r = r + " param"+str(pidx)+"="+str(p)+"\n"
            r = r + "complete command="+c+"\n" + \
                "</pre><hr>"

        r = r + command.decorateResult(self.runRawCommand(c),self,decorator)
        return r

    def runRawCommand(self,command):
        """ Abstract method. """
        raise Exception("runRawCommand() method not supported for the abstract class Router. Inherit from the class and implement the method.")

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

