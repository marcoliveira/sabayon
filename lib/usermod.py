#!/usr/bin/env python

#
# Copyright (C) 2005 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import util
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_USERMOD, fmt % args)

def set_shell (username, shell):
    argv = USERMOD_ARGV + [ "-s", shell, username ]
    dprint ("Executing %s" % argv)
    os.spawnv (os.P_WAIT, argv[0], argv)

def set_homedir (username, homedir):
    argv = USERMOD_ARGV + [ "-d", homedir, username ]
    dprint ("Executing %s" % argv)
    os.spawnv (os.P_WAIT, argv[0], argv)
