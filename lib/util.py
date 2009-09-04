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
import fnmatch
import pwd
import grp
import gettext
import locale
import errno
import random
from config import *

# Standard exit codes for helper programs (sabayon-apply, sabayon-session)
EXIT_CODE_NORMAL = 0
EXIT_CODE_FATAL = 1
EXIT_CODE_RECOVERABLE = 2
EXIT_CODE_NO_USER_PROFILE = 3 # only for sabayon-apply

_util_admin_log_config_filename = None
_util_readable_log_config_filename = None

def get_admin_log_config_filename ():
    """Returns the human-readable filename used for log configuration,
    as stored with set_log_config_filename().  This is the file that the
    system administrator actually modifies to set up the log configuration."""
    global _util_admin_log_config_filename
    return _util_admin_log_config_filename

def set_admin_log_config_filename (str):
    """Stores the filename of the human-readable configuration file which the
    system administrator used to set up the log configuration.  This can be
    queried back with get_admin_log_config_filename()."""
    global _util_admin_log_config_filename
    _util_admin_log_config_filename = str

def get_readable_log_config_filename ():
    """Returns the filename that the program actually used to read the log configuration,
    as stored with set_readable_log_config_filename().  This may be different from the
    filename from get_admin_log_config_filename(), since the helper processes in Sabayon
    may need to be given a temporary file to read their log configuration (as root's
    human-readable file may not be readable by the helper processes)."""
    global _util_readable_log_config_filename
    return _util_readable_log_config_filename

def set_readable_log_config_filename (str):
    """Stores the filename that the program actually used to read the log configuration.
    This can be queried back with get_readable_log_config_filename().  This may be different from the
    filename from get_admin_log_config_filename(), since the helper processes in Sabayon
    may need to be given a temporary file to read their log configuration (as root's
    human-readable file may not be readable by the helper processes)."""
    global _util_readable_log_config_filename
    _util_readable_log_config_filename = str

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

def get_group_membership ():
    """Returns a list of non-primary, non-system groups that the user belongs
    to.  Raises a GeneralError if this fails.  May return an empty list.
    """

    groups = grp.getgrall()

    try:
        pw = pwd.getpwuid (os.getuid ())
        user = pw[0]
    except KeyError:
        if os.environ.has_key("USER"):
            user = os.environ["USER"]
        else:
            raise GeneralError (_("Cannot find username: not set in /etc/passwd and no value for $USER in environment"))

    members = []

    for group in groups:
        if group[0] in members:
            continue
        if group[2] < 500:
            continue
        if group[0] == user:
            continue
        if user in group[3]:
            members.append(group[0])

    return members

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
    util.init_gettext() at the entry point to any script and you'll be
    able to use _(), gettext(), and ngettext() to mark strings for
    translation."""
    try:
         locale.setlocale (locale.LC_ALL, "")
    except locale.Error:
         pass
    gettext.install (PACKAGE, LOCALEDIR)
    # Python 2.4 compatibility
    import __builtin__
    __builtin__.__dict__['gettext'] = __builtin__.__dict__['_']
    __builtin__.__dict__['ngettext'] = gettext.ngettext

def random_string (len):
    """Returns a string with random binary data of the specified length"""
    bin = ""
    while len > 0:
        len = len - 1
        bin = bin + chr(random.getrandbits(8))
    return bin


def split_path(path, head=None, tail=None):
    '''Given a path split it into a head and tail. If head is passed then
    it is assumed to comprise the first part of the full path. If tail is
    passed it is assumed to comprise the second part of the full path.
    The path, head, and tail are made canonical via os.path.normpath prior
    to the operations. ValueErrors are raised if head is not present at the
    start of the path or if the path does not end with tail. The split must
    occur on a directory separator boundary.

    The return value is the tuple (head, tail) in canonical form.'''
    path = os.path.normpath(path)

    if tail is not None:
        tail = os.path.normpath(tail)
        if tail[0] == '/':
            tail = tail[1:]
        if not path.endswith(tail):
            raise ValueError
        path_len = len (path)
        tail_len = len (tail)
        dir_split = path_len - tail_len - 1
        if path[dir_split] != '/':
            raise ValueError
        return (path[:dir_split], path[dir_split+1:])

    if head is not None:
        head = os.path.normpath(head)
        if head[-1] == '/':
            head = head[:-1]
        if not path.startswith(head):
            raise ValueError
        head_len = len (head)
        dir_split = head_len
        if path[dir_split] != '/':
            raise ValueError
        return (path[:dir_split], path[dir_split+1:])

    raise ValueError

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


def should_ignore_dir (base_dir, ignore_dir_list, dir):
    dir = os.path.normpath (dir)

    for ignore_dir in ignore_dir_list:
        ignore_path = os.path.normpath (os.path.join (base_dir, ignore_dir))

        if fnmatch.fnmatch (dir, ignore_path):
            return True

    parent = os.path.dirname (dir)
    if parent != dir:
        return should_ignore_dir (base_dir, ignore_dir_list, parent)
    else:
        return False

def should_ignore_file (base_dir, ignore_dir_list, ignore_file_list, file):
    file = os.path.normpath (file)

    for ignore_file in ignore_file_list:
        ignore_path = os.path.normpath (os.path.join (base_dir, ignore_file))

        if fnmatch.fnmatch (file, ignore_path):
            return True

    return should_ignore_dir (base_dir, ignore_dir_list, os.path.dirname (file))
