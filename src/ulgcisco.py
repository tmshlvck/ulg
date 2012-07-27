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

# module globals
STRING_EXPECT_SSH_NEWKEY='Are you sure you want to continue connecting'
STRING_EXPECT_PASSWORD='(P|p)assword:'
STRING_EXPECT_SHELL_PROMPT_REGEXP = '\n[a-zA-Z0-9\._-]+>'

BGP_IPV6_TABLE_SPLITLINE_REGEXP='^\s*[0-9a-fA-F:]+\s*$'
BGP_IPV6_TABLE_HEADER_REGEXP='^\s*(Neighbor)\s+(V)\s+(AS)\s+(MsgRcvd)\s+(MsgSent)\s+(TblVer)\s+(InQ)\s+(OutQ)\s+(Up/Down)\s+(State/PfxRcd)\s*$'
BGP_IPV6_TABLE_LINE_REGEXP='^\s*([0-9a-fA-F:]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([a-zA-Z0-9:]+)\s+([a-zA-Z0-9]+|[a-zA-Z0-9]+\s\(Admin\))\s*$'
BGP_IPV4_TABLE_LINE_REGEXP='^\s*([0-9\.]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([a-zA-Z0-9:]+)\s+([a-zA-Z0-9]+|[a-zA-Z0-9]+\s\(Admin\))\s*$'
BGP_IPV4_TABLE_HEADER_REGEXP='^\s*(Neighbor)\s+(V)\s+(AS)\s+(MsgRcvd)\s+(MsgSent)\s+(TblVer)\s+(InQ)\s+(OutQ)\s+(Up/Down)\s+(State/PfxRcd)\s*$'

RESCAN_BGP_IPv4_COMMAND='show bgp ipv4 unicast summary'
RESCAN_BGP_IPv6_COMMAND='show bgp ipv6 unicast summary'

IPV4_SUBNET_REGEXP = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2}){0,1}]$'
IPV4_ADDRESS_REGEXP = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
IPV6_SUBNET_REGEXP = '^[0-9a-fA-F:]+(/[0-9]{1,2}){0,1}$'
IPV6_ADDRESS_REGEXP = '^[0-9a-fA-F:]+$'
MAC_ADDRESS_REGEXP = '^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$'


def normalizeBGPIPv6SplitLines(lines):
    """This function concatenates lines with longer IPv6 addresses that
    router splits (for no obvious reason)."""
    result = []
    slr = re.compile(BGP_IPV6_TABLE_SPLITLINE_REGEXP)
    b = None
    
    for l in lines:
        if(b):
            result.append(b + l)
            b = None
        elif(slr.match(l)):
            b = l
        else:
            result.append(l)
            
    return result

# classes

class CiscoCommandBgpIPv46Sum(ulgmodel.TextCommand):
    """ Abstract class, baseline for IPv4 and IPv6 versions. """

    def __init__(self,name=None,peer_address_command=None,peer_received_command=None):
        self.command=self.COMMAND_TEXT
        self.param_specs=[]
        self.peer_address_command = peer_address_command
        self.peer_received_command = peer_received_command

        if(name==None):
            if(self.param_specs):
                self.name=self.command % tuple([('<'+str(c.getName())+'>') for c in self.param_specs])
            else:
                self.name=self.command
        else:
            self.name = name


    def _getPeerURL(self,decorator_helper,router,peer_address):
        if decorator_helper and self.peer_address_command:
            return decorator_helper.getRuncommandURL({'routerid':str(decorator_helper.getRouterID(router)),
                                                      'commandid':str(decorator_helper.getCommandID(router,self.peer_address_command)),
                                                      'param0':peer_address})
        else:
            return None


    def _getPeerReceivedURL(self,decorator_helper,router,peer_address):
        if decorator_helper and self.peer_received_command:
            return decorator_helper.getRuncommandURL({'routerid':str(decorator_helper.getRouterID(router)),
                                                      'commandid':str(decorator_helper.getCommandID(router,self.peer_received_command)),
                                                      'param0':peer_address})
        else:
            return None


    def _getPeerTableCell(self,decorator_helper,router,peer):
        url = self._getPeerURL(decorator_helper,router,peer)
        if url:
            return decorator_helper.ahref(url,peer)
        else:
            return peer


    def _getReceivedTableCell(self,decorator_helper,router,peer,received):
        if re.compile('[0-9]+').match(received):
            url = self._getPeerReceivedURL(decorator_helper,router,peer)
            if url:
                return decorator_helper.ahref(url,received)
            else:
                return received
        else:
            return received


    def _decorateTableLine(self,line,decorator_helper,router):
        lrm = re.compile(self.table_line_regexp).match(line)
        if(lrm):
            # color selection
            if(lrm.group(10) in self.YELLOW_STATES):
                color = ulgmodel.TableDecorator.YELLOW
            elif(lrm.group(10) in self.RED_STATES):
                color = ulgmodel.TableDecorator.RED
            else:
                color = ulgmodel.TableDecorator.GREEN

            # generate table content
            return [
                (self._getPeerTableCell(decorator_helper,router,lrm.group(1)),color),
                (lrm.group(2),color),
                (decorator_helper.ahref(defaults.getASNURL(lrm.group(3)),lrm.group(3)),color),
                (lrm.group(4),color),
                (lrm.group(5),color),
                (lrm.group(6),color),
                (lrm.group(7),color),
                (lrm.group(8),color),
                (lrm.group(9),color),
                (self._getReceivedTableCell(decorator_helper,router,lrm.group(1),lrm.group(10)),color),
                ]
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
        header_regexp = re.compile(self.table_header_regexp)
        line_regexp = re.compile(self.table_line_regexp)
        for l in lines:
            if(tb):
                # inside table body
                table.append(self._decorateTableLine(l,decorator_helper,router))

            else:
                # should we switch to table body?
                thrm = header_regexp.match(l)
                if(thrm):
                    tb = True
                    table_header = [g for g in thrm.groups()]
                else:
                    # not yet in the table body, append before-table section
                    before = before + l + '\n'

        return ulgmodel.TableDecorator(table,table_header,before=decorator_helper.pre(before)).decorate()


class CiscoCommandBgpIPv4Sum(CiscoCommandBgpIPv46Sum):
    COMMAND_TEXT='show bgp ipv4 unicast summary'
    table_line_regexp=BGP_IPV4_TABLE_LINE_REGEXP
    table_header_regexp=BGP_IPV4_TABLE_HEADER_REGEXP
    RED_STATES = ['Idle', 'Active']
    YELLOW_STATES = ['Idle (Admin)',]


    def __init__(self,name=None,peer_address_command=None,peer_received_command=None):
        return CiscoCommandBgpIPv46Sum.__init__(self,name,peer_address_command,peer_received_command)


class CiscoCommandBgpIPv6Sum(CiscoCommandBgpIPv46Sum):
    COMMAND_TEXT='show bgp ipv6 unicast summary'
    table_line_regexp=BGP_IPV6_TABLE_LINE_REGEXP
    table_header_regexp=BGP_IPV6_TABLE_HEADER_REGEXP
    RED_STATES = ['Idle', 'Active']
    YELLOW_STATES = ['Idle (Admin)',]


    def __init__(self,name=None,peer_address_command=None,peer_received_command=None):
        return CiscoCommandBgpIPv46Sum.__init__(self,name,peer_address_command,peer_received_command)


    def decorateResult(self,result,router=None,decorator_helper=None):
        res=''
        for l in normalizeBGPIPv6SplitLines(str.splitlines(result)):
            res = res + "\n" + l

        return super(CiscoCommandBgpIPv6Sum,self).decorateResult(res,router,decorator_helper)


class CiscoCommandShowBgpIPv46Select(ulgmodel.TextCommand):
    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                      name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class CiscoCommandShowBgpIPv4Neigh(CiscoCommandShowBgpIPv46Select):
    COMMAND_TEXT='show bgp ipv4 unicast neighbor %s'

class CiscoCommandShowBgpIPv6Neigh(CiscoCommandShowBgpIPv46Select):
    COMMAND_TEXT='show bgp ipv6 unicast neighbor %s'

class CiscoCommandShowBgpIPv4NeighAdv(CiscoCommandShowBgpIPv46Select):
    COMMAND_TEXT='show bgp ipv4 unicast neighbor %s advertised'

class CiscoCommandShowBgpIPv6NeighAdv(CiscoCommandShowBgpIPv46Select):
    COMMAND_TEXT='show bgp ipv6 unicast neighbor %s advertised'

class CiscoCommandShowBgpIPv4NeighRecv(CiscoCommandShowBgpIPv46Select):
    COMMAND_TEXT='show bgp ipv4 unicast neighbor %s received-routes'

class CiscoCommandShowBgpIPv6NeighRecv(CiscoCommandShowBgpIPv46Select):
    COMMAND_TEXT='show bgp ipv6 unicast neighbor %s received-routes'

class CiscoRouter(ulgmodel.RemoteRouter):
    PS_KEY_BGPV4 = '-bgpipv4'
    PS_KEY_BGPV6 = '-bgpipv6'

    def _getDefaultCommands(self):
        _show_bgp_ipv4_uni_neigh = CiscoCommandShowBgpIPv4Neigh(self.getBGPIPv4Peers())
        _show_bgp_ipv4_uni_neigh_advertised = CiscoCommandShowBgpIPv4NeighAdv(self.getBGPIPv4Peers())
        _show_bgp_ipv4_uni_neigh_received_routes = CiscoCommandShowBgpIPv4NeighRecv(self.getBGPIPv4Peers())
        _show_bgp_ipv6_uni_neigh = CiscoCommandShowBgpIPv6Neigh(self.getBGPIPv6Peers())
        _show_bgp_ipv6_uni_neigh_advertised = CiscoCommandShowBgpIPv6NeighAdv(self.getBGPIPv6Peers())
        _show_bgp_ipv6_uni_neigh_received_routes = CiscoCommandShowBgpIPv6NeighRecv(self.getBGPIPv6Peers())

        return [ulgmodel.TextCommand('show version'),
                ulgmodel.TextCommand('show interfaces status'),
                CiscoCommandBgpIPv4Sum('show bgp ipv4 unicast summary',
                                        peer_address_command=_show_bgp_ipv4_uni_neigh,
                                       peer_received_command=_show_bgp_ipv4_uni_neigh_received_routes),
                CiscoCommandBgpIPv6Sum('show bgp ipv6 unicast summary',
                                       peer_address_command=_show_bgp_ipv6_uni_neigh,
                                       peer_received_command=_show_bgp_ipv6_uni_neigh_received_routes),
                _show_bgp_ipv4_uni_neigh,
                _show_bgp_ipv6_uni_neigh,
                _show_bgp_ipv4_uni_neigh_received_routes,
                _show_bgp_ipv6_uni_neigh_received_routes,
                _show_bgp_ipv4_uni_neigh_advertised,
                _show_bgp_ipv6_uni_neigh_advertised,

                ulgmodel.TextCommand('show ip route %s',[ulgmodel.TextParameter(IPV4_ADDRESS_REGEXP,name=defaults.STRING_IPADDRESS)]),
                ulgmodel.TextCommand('show ipv6 unicast route %s',[ulgmodel.TextParameter(IPV6_ADDRESS_REGEXP,name=defaults.STRING_IPADDRESS)]),
                ulgmodel.TextCommand('show ip arp %s',[ulgmodel.TextParameter('.*',name=defaults.STRING_NONEORINTORIPADDRESS)]),
                ulgmodel.TextCommand('show ipv6 neighbors %s',[ulgmodel.TextParameter('.*',name=defaults.STRING_NONEORINTORIPADDRESS)]),
                ulgmodel.TextCommand('show mac-address-table address %s',[ulgmodel.TextParameter(MAC_ADDRESS_REGEXP,name=defaults.STRING_MACADDRESS)]),
                ulgmodel.TextCommand('show mac-address-table interface %s',[ulgmodel.TextParameter('.*',name=defaults.STRING_INTERFACE)]),
                ]

    def __init__(self, host, user, password, port=22, commands=None, enable_bgp=True):
        self.setHost(host)
        self.setPort(port)
        self.setUser(user)
        self.setPassword(password)
        self.bgp_ipv4_peers = []
        self.bgp_ipv6_peers = []
        self.setName(host)

        if enable_bgp:
            if(defaults.rescan_on_display):
                self.rescanHook()
            else:
                self.loadBGPPeers()

        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(self._getDefaultCommands())


    def getForkNeeded(self):
        return True

    def rescanBGPPeers(self,command,regexp,ipv6=True):
        table = self.runRawCommand(command)

        peers = []
        rlr = re.compile(regexp)
        if ipv6:
            lines = normalizeBGPIPv6SplitLines(str.splitlines(table))
        else:
            lines = str.splitlines(table)
        for tl in lines:
            rlrm = rlr.match(tl)
            if(rlrm):
                peers.append(rlrm.group(1))

        return peers

    def rescanBGPIPv4Peers(self):
        self.bgp_ipv4_peers = self.rescanBGPPeers(RESCAN_BGP_IPv4_COMMAND,BGP_IPV4_TABLE_LINE_REGEXP,False)

    def rescanBGPIPv6Peers(self):
        self.bgp_ipv6_peers = self.rescanBGPPeers(RESCAN_BGP_IPv6_COMMAND,BGP_IPV6_TABLE_LINE_REGEXP,True)
        
    def rescanHook(self):
        self.rescanBGPIPv4Peers()
        self.rescanBGPIPv6Peers()
        self.saveBGPPeers()

    def getBGPIPv4Peers(self):
        return self.bgp_ipv4_peers

    def getBGPIPv6Peers(self):
        return self.bgp_ipv6_peers

    def saveBGPPeers(self):
        key4 = self.getHost() + self.PS_KEY_BGPV4
        key6 = self.getHost() + self.PS_KEY_BGPV6

        ps = ulgmodel.PersistentStorage.load()
        ps.set(key4,self.getBGPIPv4Peers())
        ps.set(key6,self.getBGPIPv6Peers())
        ps.save()

    def loadBGPPeers(self):
        key4 = self.getHost() + self.PS_KEY_BGPV4
        key6 = self.getHost() + self.PS_KEY_BGPV6

        ps = ulgmodel.PersistentStorage.load()
        self.bgp_ipv4_peers = ps.get(key4)
        self.bgp_ipv6_peers = ps.get(key6)

        if(not self.getBGPIPv4Peers()) or (not self.getBGPIPv6Peers()):
            self.rescanHook()

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
        i=p.expect([STRING_EXPECT_SHELL_PROMPT_REGEXP,pexpect.EOF])
        if(i==0):
            p.sendline('terminal length 0')
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")

        i=p.expect([STRING_EXPECT_SHELL_PROMPT_REGEXP,pexpect.EOF])
        if(i==0):
            p.sendline('terminal width 0')
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")

        i=p.expect([STRING_EXPECT_SHELL_PROMPT_REGEXP,pexpect.EOF])
        if(i==0):
            p.sendline(command)
        else:
            raise Exception("pexpect session failed: Missing shell prompt.")
        
        p.expect([STRING_EXPECT_SHELL_PROMPT_REGEXP,pexpect.EOF])

        def stripFirstLine(string):
            lines = str.splitlines(string)
            r = ''
            for l in lines[1:]:
                r = r + l + '\n'
            return r

        return stripFirstLine(p.before)
