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
import pwd

class GeneralError (Exception):
    def __init__ (self, msg):
        Exception.__init__ (self, msg)

unit_tests_homedir = None
def set_home_dir_for_unit_tests (homedir):
    global unit_tests_homedir
    unit_tests_homedir = homedir

def get_home_dir ():
    if unit_tests_homedir:
        return unit_tests_homedir
    try:
        pw = pwd.getpwuid (os.getuid ())
        if pw.pw_dir != "":
            return pw.pw_dir
    except KeyError:
        pass
    
    if os.environ.has_key ("HOME"):
        return os.environ["HOME"]
    else:
        raise GeneralError ("Cannot find home directory: not set in /etc/passwd and no value for $HOME in environment")

def get_user_name ():
    try:
        pw = pwd.getpwuid (os.getuid ())
        if pw.pw_name != "":
            return pw.pw_name
    except KeyError:
        pass
    
    if os.environ.has_key ("USER"):
        return os.environ["USER"]
    else:
        raise GeneralError ("Cannot find username: not set in /etc/passwd and no value for $USER in environment")

def print_exception ():
    import traceback
    import sys
    traceback.print_exc(file=sys.stderr)

def run_unit_tests ():
    home_dir = get_home_dir ()
    assert home_dir != ""
    assert get_user_name () != ""
    set_home_dir_for_unit_tests ("foo")
    assert get_home_dir () == "foo"
    set_home_dir_for_unit_tests (None)
    assert get_home_dir () == home_dir
