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
import sys
import pwd

(
    DEBUG_USERPROFILE,
    DEBUG_STORAGE,
    DEBUG_PROTOSESSION,
    DEBUG_USERMOD,
    DEBUG_DIRMONITOR,
    DEBUG_GCONFSOURCE,
    DEBUG_PANELDELEGATE,
    DEBUG_FILESSOURCE,
    DEBUG_MOZILLASOURCE,
    DEBUG_ADMINTOOL
) = range (10)

debug_modules = {
    DEBUG_USERPROFILE   : ("user-profile",   False),
    DEBUG_STORAGE       : ("storage",        False),
    DEBUG_PROTOSESSION  : ("proto-session",  False),
    DEBUG_USERMOD       : ("usermod",        False),
    DEBUG_DIRMONITOR    : ("dir-monitor",    False),
    DEBUG_GCONFSOURCE   : ("gconf-source",   False),
    DEBUG_PANELDELEGATE : ("panel-delegate", False),
    DEBUG_FILESSOURCE   : ("files-source",   False),
    DEBUG_MOZILLASOURCE : ("mozilla-source", False),
    DEBUG_ADMINTOOL     : ("admin-tool",     False)
}

def init_debug_modules ():
    debug_value = os.getenv ("SABAYON_DEBUG")
    if not debug_value:
        return

    if debug_value == "help":
        print "Valid options for the SABAYON_DEBUG environment variable are:\n"
        print "    all"
        for module in debug_modules:
            print "    %s" % debug_modules[module][0]
        sys.exit (1)
    elif debug_value == "all":
        for module in debug_modules:
            debug_modules[module] = (debug_modules[module][0], True)
    else:
        for key in debug_value.split (":"):
            for module in debug_modules:
                if debug_modules[module][0] == key:
                    debug_modules[module] = (key, True)
                    break

init_debug_modules ()

def debug_print (module, fmt, *args):
    assert debug_modules.has_key(module)
    if not debug_modules[module][1]:
        return
    print "(%d) %s: %s" % (os.getpid (), debug_modules[module][0], fmt % args)

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
