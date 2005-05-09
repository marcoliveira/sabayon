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
import os.path
import tempfile
import shutil
import util
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_USERMOD, fmt % args)

def set_shell (username, shell):
    argv = USERMOD_ARGV + [ "-s", shell, username ]
    dprint ("Executing %s" % argv)
    util.uninterruptible_spawnv (os.P_WAIT, argv[0], argv)

#
# FIXME:
#  we're fairly screwed if there's another gamin, gconfd-2
#  or whatever already running when we do this. We probably
#  should just shut them down.
#
def set_homedir (username, homedir):
    argv = USERMOD_ARGV + [ "-d", homedir, username ]
    dprint ("Executing %s" % argv)
    util.uninterruptible_spawnv (os.P_WAIT, argv[0], argv)

def create_temporary_homedir (uid, gid):
    temp_homedir = tempfile.mkdtemp (prefix = "sabayon-temp-home-")

    def copy_tree (src, dst, uid, gid):
        for file in os.listdir (src):
            src_path = os.path.join (src, file)
            dst_path = os.path.join (dst, file)

            if os.path.islink (src_path):
                linkto = os.readlink (src_path)
                os.symlink (linkto, dst_path)
            elif os.path.isdir (src_path):
                os.mkdir (dst_path)
                copy_tree (src_path, dst_path, uid, gid)
            else:
                shutil.copy2 (src_path, dst_path)
            
            os.chown (dst_path, uid, gid)

    copy_tree (SKEL_HOMEDIR, temp_homedir, uid, gid)
    os.chown (temp_homedir, uid, gid)
    return temp_homedir
