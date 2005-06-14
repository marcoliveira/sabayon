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
import sys
import pwd
import gettext
import locale
import errno
from config import *

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
    DEBUG_ADMINTOOL,
    DEBUG_USERDB,
    DEBUG_CACHE,
) = range (12)

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
    DEBUG_ADMINTOOL     : ("admin-tool",     False),
    DEBUG_USERDB        : ("user-db",        False),
    DEBUG_CACHE         : ("cache",          False),
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
        print "You may supply a list of modules separated by a colon (:)"
        print "You may also supply an optional hex debug mask to a module, e.g. foo=0xF8"
        sys.exit (1)
    elif debug_value == "all":
        for module in debug_modules:
            debug_modules[module] = (debug_modules[module][0], True)
    else:
        for item in debug_value.split (":"):
            item = item.split("=")
            key = item[0]
            if len(item) > 1:
                value = int(item[1],16)
            else:
                value = ~0
            for module in debug_modules:
                if debug_modules[module][0] == key:
                    debug_modules[module] = (key, value)
                    break

init_debug_modules ()

def debug_print (module, message, mask=~0):
    assert debug_modules.has_key(module)
    if not debug_modules[module][1] & mask:
        return
    print "(%d) %s: %s" % (os.getpid (), debug_modules[module][0], message)

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
        raise GeneralError (_("Cannot find home directory: not set in /etc/passwd and no value for $HOME in environment"))

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
        raise GeneralError (_("Cannot find username: not set in /etc/passwd and no value for $USER in environment"))

def print_exception ():
    import traceback
    import sys
    traceback.print_exc(file=sys.stderr)

def init_gettext ():
    """Binds _() to gettext.gettext() in the global namespace. Run
    util.init_gettext() at the entry point to any script and you'll
    be able to use _() to mark strings for translation.
    """
    locale.setlocale (locale.LC_ALL, "")
    gettext.install (PACKAGE, os.path.join (DATADIR, "locale"))

#
# os.spawn() doesn't handle EINTR from waitpid() on Linux:
#  http://sourceforge.net/tracker/?group_id=5470&atid=105470&func=detail&aid=686667
# Best we can do is ignore the exception and carry on
# See bug #303034
#
def uninterruptible_spawnve (mode, file, args, env):
    try:
        if env is None:
            os.spawnv (mode, file, args)
        else:
            os.spawnve (mode, file, args, env)
    except os.error, (err, errstr):
        if err != errno.EINTR:
            raise
        
def uninterruptible_spawnv (mode, file, args):
    uninterruptible_spawnve (mode, file, args, None)

def run_unit_tests ():
    home_dir = get_home_dir ()
    assert home_dir != ""
    assert get_user_name () != ""
    set_home_dir_for_unit_tests ("foo")
    assert get_home_dir () == "foo"
    set_home_dir_for_unit_tests (None)
    assert get_home_dir () == home_dir

# ------ Class DictCompare ------

class DictCompare:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def compare(self):
        ''' Given two dictionaries a,b analyze them for their
        differences and similarities.

        intersection - keys shared between a and b
        only_a       - keys only present in a
        only_b       - keys only present in b
        equal        - keys present in both a and b whole values are equal
        not_equal    - keys present in both a and b whole values are not equal'''

        self.keys_a = self.a.keys()
        self.keys_b = self.b.keys()
        
        self.intersection = []
        self.only_a = []
        self.only_b = []
        self.equal = []
        self.not_equal = []
        self._add = {}
        self._del = {}
        self._mod = {}

        for k in self.keys_a:
            if self.b.has_key(k):
                self.intersection.append(k)
            else:
                self.only_a.append(k)

        for k in self.keys_b:
            if not self.a.has_key(k):
                self.only_b.append(k)
                
        for k in self.intersection:
            if self.a[k] == self.b[k]:
                self.equal.append(k)
            else:
                self.not_equal.append(k)
                
    def intersection(self):
        'return list of keys shared between a and b'
        return self.intersection

    def only_a(self):
        'return list of keys only present in a'
        return self.only_a

    def only_b(self):
        'return list of keys only present in b'
        return self.only_b

    def equal(self):
        'return list of keys present in both a and b whole values are equal'
        return self.equal

    def not_equal(self):
        'return list of keys present in both a and b whole values are not equal'
        return self.not_equal

    def get_change_set(self, dict_lhs, dict_rhs):
        '''Return changes necessary to make dict_lhs equivalent to dict_rhs,
        (e.g. lhs = rhs), the two dictionary parameters are specified as
        either the string 'a' or the string 'b' corresponding to the parameters
        this class was created with.
        
        Return value is a dictionary with 3 keys (add, del, mod) whose values
        are dictionaries containing containing (key,value) pairs to add,
        delete, or modify respectively in dict_lhs.'''

        if dict_lhs == dict_rhs or dict_lhs not in "ab" or dict_rhs not in "ab":
            raise ValueError

        if dict_lhs == 'a':
            a = self.a
            b = self.b
            only_a = self.only_a
            only_b = self.only_b
        elif dict_lhs == 'b':
            a = self.b
            b = self.a
            only_a = self.only_b
            only_b = self.only_a
        else:
            raise ValueError

        self._add = {}
        for k in only_b:
            self._add[k] = b[k]

        self._del = {}
        for k in only_a:
            self._del[k] = a[k]

        self._mod = {}
        for k in self.not_equal:
            self._mod[k] = b[k]

        change_set = {'add':self._add, 'del':self._del, 'mod':self._mod}
        return change_set


    def is_equal(self):
        if len(self.only_a) == 0 and len(self.only_b) == 0 and len(self.not_equal) == 0:
            return True
        else:
            return False

    def dump(self):
        'Print the results of the dictionary comparision'
        print "intersection = %s" % ",".join(self.intersection)
        print "only a = %s" % ",".join(self.only_a)
        print "only b = %s" % ",".join(self.only_b)
        print "equal = %s" % ",".join(self.equal)
        print "not equal = %s" % ",".join(self.not_equal)

def dump_change_set(cs):
    _add = cs['add']
    _del = cs['del']
    _mod = cs['mod']

    if len(_add.keys()):
        print "Key/Values to ADD"
        for k in _add.keys():
            print "    %s=%s" % (k, _add[k])

    if len(_del.keys()):
        print "Keys to DELETE"
        for k in _del.keys():
            print "    %s=%s" % (k, _del[k])

    if len(_mod.keys()):
        print "Key/Values to Modify"
        for k in _mod.keys():
            print "    %s=%s" % (k, _mod[k])


