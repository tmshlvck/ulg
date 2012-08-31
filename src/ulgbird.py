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
import socket
import re

import defaults

import ulgmodel


"""
This is the input parsing code from client.c of BIRD:

static void
server_got_reply(char *x)
{
  int code;
  int len = 0;

  if (*x == '+')                        /* Async reply */
    PRINTF(len, ">>> %s\n", x+1);
  else if (x[0] == ' ')                 /* Continuation */
    PRINTF(len, "%s%s\n", verbose ? "     " : "", x+1);
  else if (strlen(x) > 4 &&
           sscanf(x, "%d", &code) == 1 && code >= 0 && code < 10000 &&
           (x[4] == ' ' || x[4] == '-'))
    {
      if (code)
        PRINTF(len, "%s\n", verbose ? x : x+5);
      if (x[4] == ' ')
      {
        nstate = STATE_PROMPT;
        skip_input = 0;
        return;
      }
    }
  else
    PRINTF(len, "??? <%s>\n", x);

  if (skip_input)
    return;

  if (interactive && input_initialized && (len > 0))
    {
      int lns = LINES ? LINES : 25;
      int cls = COLS ? COLS : 80;
      num_lines += (len + cls - 1) / cls; /* Divide and round up */
      if ((num_lines >= lns)  && (cstate == STATE_CMD_SERVER))
        more();
    }
}
"""

BIRD_SOCK_HEADER_REGEXP='^([0-9]+)[-\s](.+)$'
BIRD_SOCK_REPLY_END_REGEXP='^([0-9]+)\s*$'

BIRD_SHOW_PROTO_LINE_REGEXP='^\s*([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)(\s+([^\s].+)){0,1}\s*$'
BIRD_SHOW_PROTO_HEADER_REGEXP='^\s*(name)\s+(proto)\s+(table)\s+(state)\s+(since)\s+(info)\s*$'

bird_sock_header_regexp = re.compile(BIRD_SOCK_HEADER_REGEXP)
bird_sock_reply_end_regexp = re.compile(BIRD_SOCK_REPLY_END_REGEXP)

def isBirdSockTableStart(line):
    if(bird_sock_header_regexp.match(line)):
        return True
    else:
        return False


def getBirdSockCode(line):
    m = bird_sock_header_regexp.match(line)
    if(m):
        return int(m.group(1))
    else:
        None


def getBirdSockData(line):
    m = bird_sock_header_regexp.match(line)
    if(m):
        return m.group(2)
    else:
        None


def isBirdSockHeader(line):
    if(isBirdSockTableStart(line) and getBirdSockCode(line) == 2002):
        return True
    else:
        return False


def isBirdSockReplyEnd(line):
    m = bird_sock_reply_end_regexp.match(line)
    if(m):
        if(int(m.group(1)) == 0):
            return True

    return False


def isBirdSockAsyncReply(line):
    if(line[0] == '+'):
        return True
    else:
        return False


def isBirdSockReplyCont(line):
    if(line[0] == ' '):
        return True
    else:
        return False

def normalizeBirdSockLine(line):
    ulgmodel.debug("normalizeBirdSockLine: "+line)
    if(isBirdSockAsyncReply(line)):
        return ''

    if(isBirdSockHeader(line)):
        return getBirdSockData(line)

    if(isBirdSockTableStart(line)):
        return getBirdSockData(line)

    if(isBirdSockReplyCont(line)):
        return line[1:]

    if(isBirdSockReplyEnd(line)):
        return None

    raise Exception("Can not normalize line: "+line)


def parseShowProtocols(line):
    sh_proto_line_regexp = re.compile(BIRD_SHOW_PROTO_LINE_REGEXP)
    m = sh_proto_line_regexp.match(line)
    if(m):
        ulgmodel.debug("bird.parseShowProtocols matched line: "+line)
        ulgmodel.debug("bird.parseShowProtocols match results: "+str(m.groups()[0:-2]))
        res = list(m.groups()[0:5])
        if(m.group(6)):
            res.append(m.group(6))
        return res
    else:
        ulgmodel.debug("bird.parseShowProtocols failed to match line: "+line)
        return None


# classes

class BirdShowProtocolsCommand(ulgmodel.TextCommand):
    COMMAND_TEXT = 'show protocols'

    def __init__(self,name=None):
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[],name=name)

    def _decorateTableLine(self,line,router,decorator_helper):
        lg = parseShowProtocols(line)
        ulgmodel.debug("bird._decorateTableLine lg="+str(lg))
        if(lg):
            return [(lgm,ulgmodel.TableDecorator.GREEN) for lgm in lg]
        else:
            ulgmodel.log("BirdShowProtocolsCommand._decorateTableLine(): Skipping unparsable line: "+line)
            return None

    def decorateResult(self,result,router=None,decorator_helper=None):
        if((not router) or (not decorator_helper)):
            return "<pre>\n%s\n</pre>" % result
        else:
            table_header = []
            table = []
            for l in str.splitlines(result):
                if(re.match('^\s*$',l)):
                    continue

                hm = re.match(BIRD_SHOW_PROTO_HEADER_REGEXP,l)
                if(hm):
                    table_header = hm.groups()
                else:
                    tl = self._decorateTableLine(l,router,decorator_helper)
                    if(tl):
                        table.append(tl)

            return ulgmodel.TableDecorator(table,table_header).decorate()


class BirdRouterLocal(ulgmodel.LocalRouter):
    DefaultCommands = [BirdShowProtocolsCommand()]

    def __init__(self,sock=defaults.default_bird_sock,commands=None):
        super(self.__class__,self).__init__()
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(BirdRouterLocal.DefaultCommands)
        self.sock = sock
        self.setName('localhost')

    def runRawCommand(self,command):
        result=''

        try:
            # open socket to BIRD
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(defaults.default_bird_sock_timeout)
            s.connect(self.sock)

            # cretate FD for the socket
            sf=s.makefile()

            # wait for initial header
            l = sf.readline()

            # send the command string
            sf.write(command+"\n")
            sf.flush()

            # read and capture lines until the output delimiter string is hit
            while(True):
                l = sf.readline()

                # process line according to rules take out from the C code

                ulgmodel.debug("Raw received line: " + l)
                nl = normalizeBirdSockLine(l)
                if(nl == None):
                    # End of reply (0000 code)
                    ulgmodel.debug("End of reply.")
                    break
                else:
                    ulgmodel.debug("Normalized line: " + nl)
                    result=result+nl+'\n'

                # close the socket and return captured result
                s.close()

        except socket.timeout as e:
            # catch only timeout exception, while letting other exceptions pass
            result = STRING_SOCKET_TIMEOUT

        return result

#################################
    def getForkNeeded(self):
        return False
"""
    def rescanBGPPeers(self,command,regexp,ipv6=True):
        table = self.runRawCommand(command)

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

"""
