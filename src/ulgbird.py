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

class BirdRouterLocal(ulgmodel.LocalRouter):
    DefaultCommands = [ulgmodel.TextCommand('show protocols %s', [ulgmodel.TextParameter('.*')])]

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
