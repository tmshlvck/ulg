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

# HTML presentation settings
header = 'Universal looking glass test header'
refresh_interval = 5                             # interval of html refresh
usage_limit = 1                                  # maximum concurrently processed requests

# Settings defaults
always_start_thread = True
debug = False
persistent_storage_file = '/tmp/ulg.data'
session_dir = '/tmp'
usage_counter_file = '/tmp/ulg.lock'
log_file = '/tmp/ulg.log'
default_bird_sock = '/var/run/bird.ctl'

# Template dir relative to the index.py script
template_dir = 'templates'
index_template_file = 'index.html'
display_template_file = 'display.html'

# Paths to external programs
bin_ssh = '/usr/bin/ssh'

# Output (localized) strings
STRING_ANY='any'
STRING_PARAMETER='Parameter'
STRING_COMMAND='Command'
STRING_ERROR_COMMANDRUN='Error encountered while preparing or running command'
STRING_BAD_PARAMS='Verification of command or parameters failed.'
STRING_SESSION_OVERLIMIT = "<em>Limit of maximum concurrently running sessions and/or queries has been reached. The command can not be executed now. Please try again later.</em>"
STRING_ARBITRARY_ERROR = "Error encountered. Operation aborted. See log for further details."
STRING_IPADDRESS = "IP address"
STRING_IPSUBNET = "IP subnet"
