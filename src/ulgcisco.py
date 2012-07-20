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


class CiscoCommandBgpIPv4Sum(ulgmodel.TextCommand):
    COMMAND_TEXT='show bgp ipv4 unicast summary'
    TABLE_HEADER_REGEXP='^\s*(Neighbor)\s+(V)\s+(AS)\s+(MsgRcvd)\s+(MsgSent)\s+(TblVer)\s+(InQ)\s+(OutQ)\s+(Up/Down)\s+(State/PfxRcd)\s*$'
    TABLE_LINE_REGEXP='^\s*([0-9\.]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([a-z0-9:]+)\s+([a-zA-Z0-9]+|[a-zA-Z0-9]+\s\(Admin\))\s*$'
    RED_STATES = ['Idle', 'Active']
    YELLOW_STATES = ['Idle (Admin)',]

    def __init__(self,name=None):
        self.command=CiscoCommandBgpIPv4Sum.COMMAND_TEXT
        self.param_specs=[]

        if(name==None):
            if(self.param_specs):
                self.name=self.command % tuple([('<'+str(c.getName())+'>') for c in self.param_specs])
            else:
                self.name=self.command
        else:
            self.name = name

    def _decorateTableLine(self,line,decorator_helper):
        lrm = re.compile(CiscoCommandBgpIPv4Sum.TABLE_LINE_REGEXP).match(line)
        if(lrm):
            # color selection
            if(lrm.group(10) in CiscoCommandBgpIPv4Sum.YELLOW_STATES):
                color = ulgmodel.TableDecorator.YELLOW
            elif(lrm.group(10) in CiscoCommandBgpIPv4Sum.RED_STATES):
                color = ulgmodel.TableDecorator.RED
            else:
                color = ulgmodel.TableDecorator.GREEN

            return [(lrm.group(1),color),(lrm.group(2),color),
                    (decorator_helper.ahref(defaults.getASNURL(lrm.group(3)),lrm.group(3)),color),(lrm.group(4),color),
                    (lrm.group(5),color),(lrm.group(6),color),
                    (lrm.group(7),color),(lrm.group(8),color),
                    (lrm.group(9),color),(lrm.group(10),color),]
        else:
            raise Exception("Can not parse line: "+l)

    def decorateResult(self,result,router=None,decorator_helper=None):
        if((not router) or (not decorator_helper)):
            return "<pre>\n%s\n</pre>" % result

        lines = str.splitlines(result)

        before=''
        after=''
        table=[]
        table_header=[]

        tb = False
        header_regexp = re.compile(CiscoCommandBgpIPv4Sum.TABLE_HEADER_REGEXP)
        line_regexp = re.compile(CiscoCommandBgpIPv4Sum.TABLE_LINE_REGEXP)
        for l in lines:
            if(tb):
                # inside table body
                table.append(self._decorateTableLine(l,decorator_helper))

            else:
                # not yet in the table body
                before = before + l + '\n'

                # should we switch to table body?
                thrm = header_regexp.match(l)
                if(thrm):
                    tb = True
                    table_header = [g for g in thrm.groups()]

        return ulgmodel.TableDecorator(table,table_header,'Test TableDecorator!!!',decorator_helper.pre(before)).decorate()


class CiscoRouter(ulgmodel.RemoteRouter):
    RegExIPv4Subnet = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2}){0,1}]$'
    RegExIPv4 = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
    RegExIPv6Subnet = '^[0-9a-fA-F:]+(/[0-9]{1,2}){0,1}$'
    RegExIPv6 = '^[0-9a-fA-F:]+$'

    DefaultCommands = [ulgmodel.TextCommand('show version'),
                       
                       ulgmodel.TextCommand('show bgp ipv4 unicast %s', [ulgmodel.TextParameter(RegExIPv4Subnet,name=defaults.STRING_IPSUBNET)]),
                       ulgmodel.TextCommand('show bgp ipv6 unicast %s', [ulgmodel.TextParameter(RegExIPv6Subnet,name=defaults.STRING_IPSUBNET)]),
                       CiscoCommandBgpIPv4Sum('show bgp ipv4 unicast summary (+DECORATOR)'),
                       ulgmodel.TextCommand('show bgp ipv4 unicast summary'),
                       ulgmodel.TextCommand('show bgp ipv6 unicast summary'),
                       ulgmodel.TextCommand('show bgp ipv4 unicast neighbor %s',[ulgmodel.TextParameter(RegExIPv4,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show bgp ipv6 unicast neighbor %s',[ulgmodel.TextParameter(RegExIPv6,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show bgp ipv4 unicast neighbor %s received-routes',[ulgmodel.TextParameter(RegExIPv4,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show bgp ipv6 unicast neighbor %s received-routes',[ulgmodel.TextParameter(RegExIPv6,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show bgp ipv4 unicast neighbor %s advertised',[ulgmodel.TextParameter(RegExIPv4,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show bgp ipv6 unicast neighbor %s advertised',[ulgmodel.TextParameter(RegExIPv6,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show ip route %s',[ulgmodel.TextParameter(RegExIPv4,name=defaults.STRING_IPADDRESS)]),
                       ulgmodel.TextCommand('show ipv6 unicast route %s',[ulgmodel.TextParameter(RegExIPv6,name=defaults.STRING_IPADDRESS)]),
                       
#                      ulgmodel.TextCommand('show bgp ipv4 uni neighbor',[ulgmodel.SelectionParameter([('91.210.16.1','91.210.16.1'),('91.210.16.2','91.210.16.2'),('91.210.16.3','91.210.16.3')],name=defaults.STRING_IPADDRESS)]),

                       
                       ]
    STRING_SHELL_PROMPT_REGEXP = '\n[a-zA-Z0-9\._-]+>'

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
        i=p.expect([CiscoRouter.STRING_SHELL_PROMPT_REGEXP,pexpect.EOF])
        if(i==0):
            p.sendline('terminal length 0')
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")

        i=p.expect([CiscoRouter.STRING_SHELL_PROMPT_REGEXP,pexpect.EOF])
        if(i==0):
            p.sendline('terminal width 0')
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")

        i=p.expect([CiscoRouter.STRING_SHELL_PROMPT_REGEXP,pexpect.EOF])
        if(i==0):
            p.sendline(command)
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")
        
        p.expect([CiscoRouter.STRING_SHELL_PROMPT_REGEXP,pexpect.EOF])

        def stripFirstLine(string):
            lines = str.splitlines(string)
            r = ''
            for l in lines[1:]:
                r = r + l + '\n'
            return r

        return stripFirstLine(p.before)
