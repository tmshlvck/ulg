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
import pexpect
import re

import defaults

import ulgmodel

STRING_EXPECT_SSH_NEWKEY='Are you sure you want to continue connecting'
STRING_EXPECT_PASSWORD='(P|p)assword:'


class CiscoRouter(ulgmodel.RemoteRouter):
    DefaultCommands = [ulgmodel.TextCommand('show version'),
                       ulgmodel.TextCommand('show ip bgp', [ulgmodel.TextParameter('^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2}){0,1}]$',name=defaults.STRING_IPSUBNET)]),
                       ulgmodel.TextCommand('show bgp ipv4 uni sum'),
                       ulgmodel.TextCommand('show bgp ipv6 uni sum'),
                       ulgmodel.TextCommand('show bgp ipv4 uni neighbor',[ulgmodel.TextParameter('^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$',name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show bgp ipv4 uni neighbor',[ulgmodel.TextParameter('[0-9a-fA-F:]+)]')]),
                       ulgmodel.TextCommand('show bgp ipv4 uni neighbor',[ulgmodel.SelectionParameter([('91.210.16.1','91.210.16.1'),('91.210.16.2','91.210.16.2'),('91.210.16.3','91.210.16.3')],name=defaults.STRING_IPADDRESS)]),
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

        def stripFirstLine(string):
            lines = str.splitlines(string)
            r = ''
            for l in lines[1:]:
                r = r + l + '\n'
            return r

        return stripFirstLine(p.before)
