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

class GeneralError (Exception):
    def __init__ (self, msg):
        Exception.__init__ (self, msg)

def get_home_dir ():
    #
    # FIXME: try pull $HOME from the user's passwd entry rather
    #        than from os.environ - just like g_get_home_dir()
    #
    if os.environ.has_key ("HOME"):
        return os.environ["HOME"]
    else:
        raise GeneralError ("No value for $HOME found in environment - cannot find home directory")

def get_user_name ():
    #
    # FIXME: pull username from the user's passwd entry rather
    #        than from os.environ - just like g_get_user_name()
    #
    if os.environ.has_key ("USER"):
        return os.environ["USER"]
    else:
        raise GeneralError ("No value for $USER found in environment - cannot username")

def print_exception ():
    import traceback
    import sys
    traceback.print_exc(file=sys.stderr)

def run_unit_tests ():
    def test_env_func (func, key):
        old_value = os.environ[key]
        os.environ[key] = "foo"

        assert func () == "foo"
        del os.environ[key]

        got_exception = False
        try:
            func ()
        except GeneralError:
            got_exception = True
        assert got_exception

        os.environ[key] = old_value

    test_env_func (get_home_dir, "HOME")
    test_env_func (get_user_name, "USER")
