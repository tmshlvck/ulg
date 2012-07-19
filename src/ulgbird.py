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
        # open socket to BIRD
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.sock)

        # cretate FD for the socket
        sf=s.makefile()

        # send the command string
        s.send(command)

        # read and capture lines until the output delimiter string is hit
        result=''
        for l in sf:
            if(re.compile('^0000').match(l)):
                result=result+"BREAK\n"
                break
            result=result+l

        # close the socket and return captured result
        s.close()
        return result
