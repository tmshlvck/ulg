#!/usr/bin/env python
#
# ULG - Universal Looking Glass
# (C) 2015 CZ.NIC, z.s.p.o.
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
import pexpect

import defaults

import ulgmodel

STRING_EXPECT_SSH_NEWKEY='Are you sure you want to continue connecting'
STRING_EXPECT_PASSWORD='(P|p)assword:'

class LinuxRouter(ulgmodel.Router):
    """ Abstract class representing common base for linux router objects. """

    def __init__(self):
        pass

    def _getDefaultCommands(self):
        return [ulgmodel.TextCommand("ping -c 4 %s", param_specs=[ulgmodel.IPv4AddressParameter()]),
                ulgmodel.TextCommand("ping6 -c 4 %s", param_specs=[ulgmodel.IPv6AddressParameter()]),
                ulgmodel.TextCommand("traceroute %s", param_specs=[ulgmodel.IPv4AddressParameter()]),
                ulgmodel.TextCommand("traceroute6 %s", param_specs=[ulgmodel.IPv6AddressParameter()]),
                ]

class LinuxRouterLocal(ulgmodel.LocalRouter,LinuxRouter):
    def __init__(self,commands=None,name='localhost',acl=None):
        ulgmodel.LocalRouter.__init__(self,acl=acl)
        LinuxRouter.__init__(self)

        self.setName(name)

        # command autoconfiguration might run only after other parameters are set
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(self._getDefaultCommands())


    def runRawCommand(self,command,outfile):
        s=pexpect.spawn(command,timeout=defaults.timeout)

        while True:
            i=s.expect(['\n',pexpect.EOF,pexpect.TIMEOUT])
            if (i==0):
                outfile.write(s.before)
            elif (i==1):
                break
            elif (i==2):
                raise Exception("pexpect session timed out. last output: "+s.before)
            else:
                raise Exception("pexpect session failed: Unknown error. last output: "+s.before)

    def getForkNeeded(self):
        return False


class LinuxRouterRemote(ulgmodel.RemoteRouter,LinuxRouter):
    def __init__(self,host,user,password='',port=22,commands=None,name=None,bin_ssh=None,acl=None):
        ulgmodel.RemoteRouter.__init__(self,acl=acl)
        LinuxRouter.__init__(self)

        self.setHost(host)
        self.setUser(user)
        self.setPassword(password)
        self.setPort(port)
        if(name):
            self.setName(name)
        else:
            self.setName(host)

        if(bin_ssh):
            self.bin_ssh = bin_ssh
        else:
            self.bin_ssh = defaults.bin_ssh

        # command autoconfiguration might run only after other parameters are set
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(self._getDefaultCommands())


    def getForkNeeded(self):
        return True

    def runRawCommand(self,command,outfile):
        c = '/bin/bash -c \''+self.bin_ssh+' -p'+str(self.getPort())+' '+str(self.getUser())+'@'+self.getHost()+' "'+command+'"\''
        s=pexpect.spawn(c,timeout=defaults.timeout)

        # handle ssh
        y=0
        p=0
        l=0
        capture=False
        while True:
            i=s.expect([STRING_EXPECT_SSH_NEWKEY,STRING_EXPECT_PASSWORD,'\n',pexpect.EOF,pexpect.TIMEOUT])
            if(i==0):
                if(y>1):
                    raise Exception("pexpect session failed: Can not save SSH key.")

                s.sendline('yes')
                y+=1
            elif(i==1):
                if(p>1):
                    raise Exception("pexpect session failed: Password not accepted.")

                s.sendline(self.password)
                p+=1
            elif(i==2):
                outfile.write(s.before)
            elif(i==3): # EOF -> process output
                break
            elif(i==4):
                raise Exception("pexpect session timed out. last output: "+s.before)
            else:
                raise Exception("pexpect session failed: Unknown error. last output: "+s.before)
