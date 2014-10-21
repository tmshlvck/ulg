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
import os, sys
import re
import subprocess

import defaults

ASNAME_REGEX = '^\s*(as-name|ASName):\s*([^\s].*)\s*'
asname_regex = re.compile(ASNAME_REGEX)

asname_cache = {}

def lookup(key):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    s = subprocess.Popen([defaults.bin_whois, '-H', key],
                         stdout=subprocess.PIPE)

    res=''
    begin = False
    for l in s.stdout.readlines():
        if(re.match('^\s*$',l) and not begin):
            continue
        if(l[0] != '%'):
            res=res+l.decode('utf-8','replace')
            begin = True

    return res

def lookup_as_name(asn):
    if asn in asname_cache:
        return asname_cache[asn]

    os.environ['PYTHONIOENCODING'] = 'utf-8'
    s = subprocess.Popen([defaults.bin_whois, '-H', asn],
                         stdout=subprocess.PIPE)

    for l in s.stdout.readlines():
        m = asname_regex.match(l)
        if(m):
            asname_cache[asn] = m.group(2)
            return m.group(2).decode('utf-8','replace')

    return defaults.STRING_UNKNOWN
