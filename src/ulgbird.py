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


def parseBirdShowProtocols(text):
    def parseShowProtocolsLine(line):
        sh_proto_line_regexp = re.compile(BIRD_SHOW_PROTO_LINE_REGEXP)
        m = sh_proto_line_regexp.match(line)
        if(m):
            res = list(m.groups()[0:5])
            if(m.group(6)):
                res.append(m.group(6))

            return res
        else:
            ulgmodel.log("WARN: bird.parseShowProtocolsLine failed to match line: "+line)
            return None


    header = []
    table = []
    for l in str.splitlines(text):
        if(re.match('^\s*$',l)):
            continue
        
        hm = re.match(BIRD_SHOW_PROTO_HEADER_REGEXP,l)
        if(hm):
            header = hm.groups()
        else:
            pl = parseShowProtocolsLine(l)
            if(pl):
                table.append(pl)
            else:
                ulgmodel.log("ulgbird.parseBirdShowProtocols skipping unparsable line"+l)

    return (header,table)


# classes

class BirdShowProtocolsCommand(ulgmodel.TextCommand):
    COMMAND_TEXT = 'show protocols'

    def __init__(self,name=None):
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[],name=name)

    def _decorateTableLine(self,table_line,router,decorator_helper):
        def _getTableLineColor(state):
            if(state == 'up'):
                return ulgmodel.TableDecorator.GREEN
            elif(state == 'start'):
                return ulgmodel.TableDecorator.YELLOW
            else:
                return ulgmodel.TableDecorator.RED

        color = _getTableLineColor(table_line[3])
        return [(tlg,color) for tlg in table_line]


    def decorateResult(self,result,router=None,decorator_helper=None):
        if((not router) or (not decorator_helper)):
            return "<pre>\n%s\n</pre>" % result
        else:
            pr = parseBirdShowProtocols(result)
            table_header = pr[0]
            table = []

            for tl in pr[1]:
                table.append(self._decorateTableLine(tl,router,decorator_helper))

            return ulgmodel.TableDecorator(table,table_header).decorate()


class BirdBGPPeerSelectCommand(ulgmodel.TextCommand):
    """ Abstract class for all BIRD BGP peer-specific commands """

    def __init__(self,peers,name=None):
        peer_param = ulgmodel.SelectionParameter([tuple((p,p,)) for p in peers],
                                                 name=defaults.STRING_PEERID)
        ulgmodel.TextCommand.__init__(self,self.COMMAND_TEXT,param_specs=[peer_param],name=name)

class BirdShowProtocolsAllCommand(BirdBGPPeerSelectCommand):
    COMMAND_TEXT = 'show protocols all %s'

class BirdShowRouteExportCommand(BirdBGPPeerSelectCommand):
    COMMAND_TEXT = 'show route export %s'

class BirdShowRouteProtocolCommand(BirdBGPPeerSelectCommand):
    COMMAND_TEXT = 'show route protocol %s'




class BirdRouterLocal(ulgmodel.LocalRouter):
    RESCAN_BGP_COMMAND = 'show protocols'

    def __init__(self,sock=defaults.default_bird_sock,commands=None):
        super(self.__class__,self).__init__()
        self.sock = sock
        self.setName('localhost')

        # command autoconfiguration might run only after other parameters are set
        if(commands):
            self.setCommands(commands)
        else:
            self.setCommands(self._getDefaultCommands())

    def _getDefaultCommands(self):
        return [BirdShowProtocolsCommand(),
                BirdShowProtocolsAllCommand(self.getBGPPeers()),
                BirdShowRouteProtocolCommand(self.getBGPPeers()),
                BirdShowRouteExportCommand(self.getBGPPeers()),
                ]

    def runRawCommand(self,command):
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

    def getForkNeeded(self):
        return False


    def rescanBGPPeers(self):
        res = self.runRawCommand(self.RESCAN_BGP_COMMAND)
        psp = parseBirdShowProtocols(res)

        peers = []
        for pspl in psp[1]:
            if(pspl[1] == "BGP"):
                peers.append(pspl[0])

        return peers


    def getBGPPeers(self):
        return self.rescanBGPPeers()

    def getBGPIPv6Peers(self):
        return self.bgp_ipv6_peers

