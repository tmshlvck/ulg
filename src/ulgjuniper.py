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
import socket
import re
import pexpect

import defaults

import ulgmodel
import ulggraph

JUNIPER_GRAPH_SH_ROUTE = "Graph show route <IP subnet>"

IPV46_SUBNET_REGEXP = '^[0-9a-fA-F:\.]+(/[0-9]{1,2}){0,1}$'

STRING_EXPECT_SSH_NEWKEY='Are you sure you want to continue connecting'
STRING_EXPECT_LOGIN='login:'
STRING_EXPECT_PASSWORD='(P|p)assword:'
STRING_EXPECT_SHELL_PROMPT_REGEXP = '[^\s]+> '
STRING_LOGOUT_COMMAND = 'exit'
STRING_CLI_INFINITE_COMMAND = 'set cli screen-length 0'

TABLE_LINE_REGEX = "([0-9a-fA-F:\.]+)\s+([0-9]+)\s+.*"
table_line_regex = re.compile(TABLE_LINE_REGEX)

TABLE_HEADER_REGEX = "Peer\s+AS\s+InPkt\s+OutPkt\s+OutQ\s+Flaps\s+.*"
table_header_regex = re.compile(TABLE_HEADER_REGEX)

JUNIPER_BGP_PATH_ACTIVE_REGEX = ".*(\*|\+)\[BGP/[0-9]+\].*"
juniper_bgp_path_active_regex = re.compile(JUNIPER_BGP_PATH_ACTIVE_REGEX)

JUNIPER_BGP_PATH_REGEX = ".*(-|)\[BGP/[0-9]+\].*"
juniper_bgp_path_regex = re.compile(JUNIPER_BGP_PATH_REGEX)

JUNIPER_BGP_PATH_CONTENT = ".*AS path: ([0-9\s]+).*"
juniper_bgp_path_content = re.compile(JUNIPER_BGP_PATH_CONTENT)


def jun_parse_show_bgp_sum(lines):
    peers=[]

    table_started=False
    for l in str.splitlines(lines):
        if(table_started):
            m=table_line_regex.match(l)
            if(m):
                peers.append(m.group(1))

        if(table_header_regex.match(l)):
            table_started=True

#    ulgmodel.debug("DEBUG jun_parse_show_bgp_sum: peers="+str(peers))
    return peers

def juniper_parse_sh_route(text,prependas):
    def split_ases(ases):
        return str.split(ases)

    DEFAULT_PARAMS = {'recuse':False, 'reconly':False, 'aggr':None}

    res = []

    bgp_start = False
    params = dict(DEFAULT_PARAMS)
    for l in str.splitlines(text):
        ulgmodel.debug("JUNIPER PARSE SHOW ROUTE: l="+str(l))
        if(juniper_bgp_path_active_regex.match(l)):
            ulgmodel.debug("JUNIPER PARSE SHOW ROUTE: ACTIVE PATH")
            bgp_start = True
            params['recuse']=True
            continue

        if(juniper_bgp_path_regex.match(l)):
            ulgmodel.debug("JUNIPER PARSE SHOW ROUTE: NON-ACTIVE PATH")
            bgp_start = True
            continue

        m=juniper_bgp_path_content.match(l)
        if(m and bgp_start):
            ulgmodel.debug("JUNIPER PARSE SHOW ROUTE: path="+str(m.group(1)))
            ases = [ulgmodel.annotateAS("AS"+str(asn)) for asn in [prependas] + split_ases(m.group(1))]
            res.append((ases,params))
            params = dict(DEFAULT_PARAMS)
            bgp_start = False
            continue

    ulgmodel.debug("JUNIPER PARSE SHOW ROUTE: res="+str(res))
    return res

def juniper_reduce_paths(paths):
    def assign_value(path):
        if(path[1]['recuse']):
            return 1
        elif(path[1]['reconly']):
            return 100
        else:
            return 10

    return sorted(paths,key=assign_value)

class JuniperShowBgpNeigh(ulgmodel.TextCommand):
    COMMAND_TEXT='show bgp neighbor %s'

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                 name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class JuniperShowRouteBgpAdv(ulgmodel.TextCommand):
    COMMAND_TEXT='show route advertising-protocol bgp %s'

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                 name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class JuniperShowRouteBgpRecv(ulgmodel.TextCommand):
    COMMAND_TEXT='show route receive-protocol bgp %s'

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                 name=defaults.STRING_IPADDRESS)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class JuniperShowRoute(ulgmodel.TextCommand):
    COMMAND_TEXT = 'show route %s'

    def __init__(self,name=None):
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[
                ulgmodel.TextParameter(pattern=IPV46_SUBNET_REGEXP,name=defaults.STRING_IPSUBNET),
                ],
                                      name=name)


class JuniperGraphShowRoute(ulgmodel.TextCommand):
    COMMAND_TEXT = 'show route %s'

    def __init__(self,name=JUNIPER_GRAPH_SH_ROUTE):
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[
                ulgmodel.TextParameter(pattern=IPV46_SUBNET_REGEXP,name=defaults.STRING_IPSUBNET),
                ],
                                      name=name)

    def finishHook(self,session):
        session.setData(juniper_parse_sh_route(session.getResult(),str(session.getRouter().getASN())))

    def decorateResult(self,session,decorator_helper=None):
        if(session.isFinished()):
            if(session.getData() != None) and (session.getData() != []):
                return (decorator_helper.img(decorator_helper.getSpecialContentURL(session.getSessionId()),defaults.STRING_BGP_GRAPH),1)
            else:
                return (decorator_helper.pre(defaults.STRING_BGP_GRAPH_ERROR), 1)
        else:
            return ('',0)

    def getSpecialContent(self,session,**params):
        paths = session.getData()
        print "Content-type: image/png\n"
        ulggraph.bgp_graph_gen(juniper_reduce_paths(paths),start=session.getRouter().getName(),
			       end=session.getParameters()[0])

    def showRange(self):
        return False




# ABSTRACT
class JuniperRouter(ulgmodel.RemoteRouter):
    RESCAN_PEERS_COMMAND = 'show bgp summary'

    PS_KEY_BGP = '-bgppeers'

    def __init__(self,host,user,password='',port=22,commands=None,asn='My ASN',name=None):
        ulgmodel.RemoteRouter.__init__(self)

        self.setHost(host)
        self.setUser(user)
        self.setPassword(password)
        self.setPort(port)
        if(name):
            self.setName(name)
        else:
            self.setName(host)
        self.setASN(asn)

        if(defaults.rescan_on_display):
            self.rescanHook()
        else:
            self.loadPersistentInfo()

        # command autoconfiguration might run only after other parameters are set
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(self._getDefaultCommands())


    def getForkNeeded(self):
        return True

    def _getDefaultCommands(self):
        return [ulgmodel.TextCommand('show version'),
                ulgmodel.TextCommand('show bgp summary'),
                JuniperShowRoute(),
                JuniperShowBgpNeigh(self.getBGPPeers()),
                JuniperShowRouteBgpRecv(self.getBGPPeers()),
                JuniperShowRouteBgpAdv(self.getBGPPeers()),
                JuniperGraphShowRoute(),
                ]

    def rescanPeers(self):
        res = self.runRawSyncCommand(self.RESCAN_PEERS_COMMAND)

        peers = jun_parse_show_bgp_sum(res)

        self.bgp_peers = peers

    def getBGPPeers(self):
        return self.bgp_peers

    def savePersistentInfo(self):
        key_bgp = self.getHost() + self.getName() + self.PS_KEY_BGP
        
        ps = ulgmodel.PersistentStorage.load()
        ps.set(key_bgp,self.getBGPPeers())
        ps.save()
               
    def loadPersistentInfo(self):
        key_bgp = self.getHost() + self.getName() + self.PS_KEY_BGP

        ps = ulgmodel.PersistentStorage.load()
        self.bgp_peers = ps.get(key_bgp)

        if(not self.getBGPPeers()):
            self.rescanHook()

    def rescanHook(self):
        self.rescanPeers()
        self.savePersistentInfo()


class JuniperRouterRemoteTelnet(JuniperRouter):
    def __init__(self,host,user,password='',port=23,commands=None,asn='My ASN',name=None):
        JuniperRouter.__init__(self,host=host,user=user,password=password,port=port,commands=commands,asn=asn,name=name)


    def runRawCommand(self,command,outfile):
        skiplines=1
        c = defaults.bin_telnet+' '+self.getHost()+' '+str(self.getPort())
        s=pexpect.spawn(c,timeout=defaults.timeout)

#        s.logfile = open('/tmp/ulgjuni.log', 'w')

        p=0
        while True:
            i=s.expect([STRING_EXPECT_LOGIN,STRING_EXPECT_PASSWORD,
                        STRING_EXPECT_SHELL_PROMPT_REGEXP,pexpect.EOF,pexpect.TIMEOUT])
            if(i==0):
                s.sendline(self.user)
            elif(i==1):
                if(p>1):
                    raise Exception("pexpect session failed: Password not accepted.")

                s.sendline(self.password)
                p+=1
            elif(i==2): # shell
                break
            elif(i==3): # EOF -> process output
                raise Exception("pexpect session failed to authenticate, remote server disconnected.")
            elif(i==4):
                raise Exception("pexpect session timed out. last output: "+s.before)
            else:
                raise Exception("pexpect session failed: Unknown error. last output: "+s.before)

        s.sendline(STRING_CLI_INFINITE_COMMAND)
        while True:
            i=s.expect([STRING_EXPECT_SHELL_PROMPT_REGEXP,'\n',pexpect.EOF,pexpect.TIMEOUT])
            if(i==0): # shell prompt -> proceed
                break
            if(i==1):
                pass # anything else -> ignore
            elif(i==2 or i==3):
                raise Exception("pexpect session timed out. last output: "+s.before)
            else:
                raise Exception("pexpect session failed: Unknown error. last output: "+s.before)

        s.sendline(command)
        capture=True
        line=0
        while True:
            i=s.expect([STRING_EXPECT_SHELL_PROMPT_REGEXP,'\n',pexpect.EOF,pexpect.TIMEOUT])
            if(i==0): # shell prompt -> logout
                capture=False
                s.sendline(STRING_LOGOUT_COMMAND)
            elif(i==1):
                if(capture and line >= skiplines):
                    outfile.write(s.before + "\n")
                line+=1
            elif(i==2): # EOF -> process output
                break
            elif(i==3):
                raise Exception("pexpect session timed out. last output: "+s.before)
            else:
                raise Exception("pexpect session failed: Unknown error. last output: "+s.before)

        s.expect([pexpect.EOF])


class JuniperRouterRemoteSSH(JuniperRouter):
    def __init__(self,host,user,password='',port=22,commands=None,asn='My ASN',name=None):
        JuniperRouter.__init__(self,host=host,user=user,password=password,commands=commands,asn=asn,name=name)


    def runRawCommand(self,command,outfile):
        c = defaults.bin_ssh+' -p'+str(self.getPort())+' '+str(self.getUser())+'@'+self.getHost()
        s=pexpect.spawn(c,timeout=defaults.timeout)

#        s.logfile = open('/tmp/ulgjuni.log', 'w')

        # handle ssh
        y=0
        p=0
        while True:
            i=s.expect([STRING_EXPECT_SSH_NEWKEY,STRING_EXPECT_PASSWORD,pexpect.EOF,pexpect.TIMEOUT])
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
            elif(i==2): # EOF -> process output
                break
            elif(i==3):
                raise Exception("pexpect session timed out. last output: "+s.before)
            else:
                raise Exception("pexpect session failed: Unknown error. last output: "+s.before)


        def stripFirstLines(string):
            lines = str.splitlines(string)
            r = re.sub(BIRD_CONSOLE_PROMPT_REGEXP,'',lines[2]) + '\n'
            for l in lines[3:]:
                r = r + l + '\n'
            return r

        out = s.before
#        ulgmodel.debug("BIRD OUT: "+out)
        outfile.write(stripFirstLines(out))

