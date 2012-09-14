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
import sys
import string

import defaults

import ulgmodel

# module globals
STRING_EXPECT_SSH_NEWKEY='Are you sure you want to continue connecting'
STRING_EXPECT_PASSWORD='(P|p)assword:'
STRING_EXPECT_SHELL_PROMPT_REGEXP = '\n[a-zA-Z0-9\._-]+>'
BGP_IPV6_SUM_TABLE_SPLITLINE_REGEXP='^\s*[0-9a-fA-F:]+\s*$'

BGP_IPV6_TABLE_HEADER_REGEXP='^\s*(Neighbor)\s+(V)\s+(AS)\s+(MsgRcvd)\s+(MsgSent)\s+(TblVer)\s+(InQ)\s+(OutQ)\s+(Up/Down)\s+(State/PfxRcd)\s*$'
BGP_IPV6_TABLE_LINE_REGEXP='^\s*([0-9a-fA-F:]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([a-zA-Z0-9:]+)\s+([a-zA-Z0-9\(\)]+|[a-zA-Z0-9]+\s\(Admin\))\s*$'
BGP_IPV4_TABLE_HEADER_REGEXP='^\s*(Neighbor)\s+(V)\s+(AS)\s+(MsgRcvd)\s+(MsgSent)\s+(TblVer)\s+(InQ)\s+(OutQ)\s+(Up/Down)\s+(State/PfxRcd)\s*$'
BGP_IPV4_TABLE_LINE_REGEXP='^\s*([0-9\.]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([a-zA-Z0-9:]+)\s+([a-zA-Z0-9\(\)]+|[a-zA-Z0-9]+\s\(Admin\))\s*$'

BGP_PREFIX_TABLE_HEADER='^(\s)\s+(Network)\s+(Next Hop)\s+(Metric)\s+(LocPrf)\s+(Weight)\s+(Path)\s*$'

RESCAN_BGP_IPv4_COMMAND='show bgp ipv4 unicast summary'
RESCAN_BGP_IPv6_COMMAND='show bgp ipv6 unicast summary'

IPV4_SUBNET_REGEXP = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2}){0,1}]$'
IPV4_ADDRESS_REGEXP = '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
IPV6_SUBNET_REGEXP = '^[0-9a-fA-F:]+(/[0-9]{1,2}){0,1}$'
IPV6_ADDRESS_REGEXP = '^[0-9a-fA-F:]+$'
MAC_ADDRESS_REGEXP = '^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$'

BGP_RED_STATES = ['Idle', 'Active', '(NoNeg)']
BGP_YELLOW_STATES = ['Idle (Admin)',]


def matchCiscoBGPLines(header,lines):
    # Match cisco lines formatted to be aligned to columns. Like:
    #    Network          Next Hop            Metric LocPrf Weight Path
    # *  79.170.248.0/21  91.210.16.6            300             0 20723 i
    # *>i91.199.207.0/24  217.31.48.123            0   1024      0 44672 i
    # 0  1                2                   3      4      5      6
    #
    #    Network          Next Hop            Metric LocPrf Weight Path
    # *>i2001:67C:278::/48
    #                     2001:1AB0:B0F4:FFFF::2
    #                                         0        1024      0 51278 i
    # *> 2001:1AB0::/32   ::                  0              32768 i
    # 0  1                2                   3      4      5      6
    #
    # First find boundaries, second section text (if it overflow next boundary
    # line wrap is expected) and then remove white spaces and return sections.
    #
    # ?1 hat happens when last element is line-wrapped? It looks like it does
    # not happen in my settings.

    def divideGroups(line,max_index_start=sys.maxint,table_line=False):
        # divide groups starting before max_index_start
        result = []

        # when parsing table_line (not the header and not the continuation line)
        # cut off first three charactes and use them as a group
        if(table_line and
           (not re.match('^\s*$',line[0:3]))):
            result.append([0,3])
            line = '   '+line[3:]

        last_group = False
        for r in re.compile('[^\s]+').finditer(line):
            if(not last_group):
                result.append([r.start(),r.end()])

            if(r.start() >= max_index_start):
                last_group = True

        # shortcut for empty lines / no results
        if(len(result)==0):
            return None

        # add tail to last groups
        result[-1][1] = len(line)
        return result


    def matchGroup(header_groups_indexes,line_group_indexes,last_element):
        if(len(header_groups_indexes) == 1):
            return 0

        # beginning of the second group is right of the beginning of the tested
        if((len(header_groups_indexes) > 1) and
           (header_groups_indexes[1][0] > line_group_indexes[0])):
            return 0

        # beginning of the last (and the only possible) group is left
        # the beginning of the tested
        if(header_groups_indexes[-1][0] <= line_group_indexes[0]):
            return (len(header_groups_indexes)-1)

        # linear algorithm !!!
        # rewrite to tree(?)
        for hgipos,hgi in enumerate(header_groups_indexes):

            if((hgipos >= 1) and
               (hgipos < (len(header_groups_indexes)-1)) and
               (header_groups_indexes[hgipos-1][1] <= line_group_indexes[0]) and
               (header_groups_indexes[hgipos+1][0] >= line_group_indexes[1])):
                return hgipos

            if((last_element) and
               (hgipos >= 1) and
               (hgi[0] <= line_group_indexes[0]) and
               (len(header_groups_indexes)-1 > hgipos) and
               (header_groups_indexes[hgipos+1][0] > line_group_indexes[0])):
                return hgipos

        return None


    def normalize(instr):
        return instr.strip()


    hgidxs = divideGroups(header)
    result = [[]]

    for l in lines:
        # divide groups (leave the last group in one part)
        lgps = divideGroups(l,hgidxs[-1][0],True)
        if(lgps==None):
            continue

        for lgpidx,lgp in enumerate(lgps):
            gidx = matchGroup(hgidxs,lgp,(lgpidx == (len(lgps)-1)))
            if(gidx == None):
                raise Exception("No group matched for line indexes. line="+l+" header_group_indexes="+
                                str(hgidxs)+" line_group_index="+str(lgp))


            if(gidx < len(result[-1])):
                result.append([])

            while(gidx > len(result[-1])):
                result[-1].append('')


            result[-1].append(normalize(l[lgp[0]:lgp[1]]))

    return result

def normalizeBGPIPv6SumSplitLines(lines):
    """This function concatenates lines with longer IPv6 addresses that
router splits on the header boundary."""
    result = []
    slr = re.compile(BGP_IPV6_SUM_TABLE_SPLITLINE_REGEXP)
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

    RED_STATES = BGP_RED_STATES
    YELLOW_STATES = BGP_YELLOW_STATES

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
        lrm = re.compile(self.TABLE_LINE_REGEXP).match(line)
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
            raise Exception("Can not parse line: "+line)

    def decorateResult(self,result,router=None,decorator_helper=None,resrange=0):
        if((not router) or (not decorator_helper)):
            return "<pre>\n%s\n</pre>" % result

        lines = str.splitlines(result)

        before=''
        after=''
        table=[]
        table_header=[]

        tb = False
        header_regexp = re.compile(self.TABLE_HEADER_REGEXP)
        line_regexp = re.compile(self.TABLE_LINE_REGEXP)
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

        result_len = len(table)
        table = table[resrange:resrange+defaults.range_step]

        return (ulgmodel.TableDecorator(table,table_header,before=decorator_helper.pre(before)).decorate(),result_len)


class CiscoCommandBgpIPv4Sum(CiscoCommandBgpIPv46Sum):
    COMMAND_TEXT='show bgp ipv4 unicast summary'
    TABLE_LINE_REGEXP=BGP_IPV4_TABLE_LINE_REGEXP
    TABLE_HEADER_REGEXP=BGP_IPV4_TABLE_HEADER_REGEXP

    def __init__(self,name=None,peer_address_command=None,peer_received_command=None):
        return CiscoCommandBgpIPv46Sum.__init__(self,name,peer_address_command,peer_received_command)


class CiscoCommandBgpIPv6Sum(CiscoCommandBgpIPv46Sum):
    COMMAND_TEXT='show bgp ipv6 unicast summary'
    TABLE_LINE_REGEXP=BGP_IPV6_TABLE_LINE_REGEXP
    TABLE_HEADER_REGEXP=BGP_IPV6_TABLE_HEADER_REGEXP

    def __init__(self,name=None,peer_address_command=None,peer_received_command=None):
        return CiscoCommandBgpIPv46Sum.__init__(self,name,peer_address_command,peer_received_command)

    def decorateResult(self,result,router=None,decorator_helper=None,resrange=0):
        res=''
        for l in normalizeBGPIPv6SumSplitLines(str.splitlines(result)):
            res = res + "\n" + l

        return super(CiscoCommandBgpIPv6Sum,self).decorateResult(res,router,decorator_helper,resrange)


class CiscoCommandShowBgpIPv4Neigh(ulgmodel.TextCommand):
    COMMAND_TEXT='show bgp ipv4 unicast neighbor %s'

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                 name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class CiscoCommandShowBgpIPv6Neigh(ulgmodel.TextCommand):
    COMMAND_TEXT='show bgp ipv6 unicast neighbor %s'

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                 name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class CiscoCommandShowBgpIPv46Select(ulgmodel.TextCommand):
    TABLE_HEADER_REGEXP=BGP_PREFIX_TABLE_HEADER
    LASTLINE_REGEXP='^\s*Total number of prefixes [0-9]+\s*$'

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                      name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

    def _decorateASPath(self,path,decorator_helper):
        result = ''
        for asnm in re.compile('[^\s]+').finditer(path):
            asn = asnm.group(0)
            if(asn.isdigit()):
                result = result + ' ' + decorator_helper.ahref(defaults.getASNURL(asn),asn)
            else:
                if(re.match('^\s*{[0-9,]+}\s*', asn)):
                    result = result + '{'
                    isnext = False
                    for sasnm in re.compile('[0-9]+').finditer(asn):
                        sasn = sasnm.group(0)
                        if(sasn.isdigit()):
                            if(isnext):
                                result = result + ',' + decorator_helper.ahref(defaults.getASNURL(sasn),sasn)
                            else:
                                isnext = True
                                result = result + decorator_helper.ahref(defaults.getASNURL(sasn),sasn)
                    result = result + '}'
                else:
                    result = result + ' ' +asn

        return result

    def _genTable(self,table_lines,decorator_helper,router):
        mls = matchCiscoBGPLines(self.table_header,table_lines)

        result = []
        for ml in mls:
            # generate table content
            result.append([
                    (ml[0],),
                    (decorator_helper.ahref(defaults.getIPPrefixURL(ml[1]),ml[1]),),
                    (ml[2],),
                    (ml[3],),
                    (ml[4],),
                    (ml[5],),
                    (self._decorateASPath(ml[6],decorator_helper),),
                    ])
        return result

    def decorateResult(self,result,router=None,decorator_helper=None,resrange=0):
        if((not router) or (not decorator_helper)):
            return "<pre>\n%s\n</pre>" % result

        lines = str.splitlines(result)

        before=''
        after=None
        table=[]
        table_header_descr=[]

        tb = False
        header_regexp = re.compile(self.TABLE_HEADER_REGEXP)
        lastline_regexp = re.compile(self.LASTLINE_REGEXP)
        table_lines = []
        for l in lines:
            if(tb):
                # inside table body
                if(lastline_regexp.match(l)):
                    after = l
                else:
                    table_lines.append(l)

            else:
                # should we switch to table body?
                thrm = header_regexp.match(l)
                if(thrm):
                    # set header accoring to the local router alignment
                    # include (unnamed) states (=S)
                    self.table_header = 'S'+(l[1:].replace('Next Hop','Next_Hop',1))
                    tb = True
                    table_header_descr = [g for g in thrm.groups()]
                else:
                    # not yet in the table body, append before-table section
                    before = before + l + '\n'

        result_len = len(table_lines)
        if(table_lines):
            table = self._genTable(table_lines[resrange:resrange+defaults.range_step],decorator_helper,router)

        if(after):
            after=decorator_helper.pre(after)

        return (ulgmodel.TableDecorator(table,table_header_descr,before=decorator_helper.pre(before),
                                       after=after).decorate(), result_len)

        
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
        table = self.runRawSyncCommand(command)

        peers = []
        rlr = re.compile(regexp)
        if ipv6:
            lines = normalizeBGPIPv6SumSplitLines(str.splitlines(table))
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

    def runRawCommand(self,command,outfile):
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

        outfile.write(stripFirstLine(p.before))
