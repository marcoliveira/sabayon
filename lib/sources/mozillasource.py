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

import gobject
import config
import userprofile
import exceptions, sys, os.path, ConfigParser, re, cPickle
import tempfile, types
import dirmonitor
import util
import filessource
import traceback


ini_partial_path = ".mozilla/firefox/profiles.ini"

def dprint(fmt, *args):
    util.debug_print(util.DEBUG_MOZILLASOURCE, fmt % args)

def dwarn(fmt, *args):
    print >> sys.stderr, "WARNING " + fmt % args

class MozillaChange (userprofile.ProfileChange):
    (
        CREATED,
        DELETED,
        CHANGED
    ) = range (3)
    
    def __init__ (self, source, delegate, key, value, event):
        userprofile.ProfileChange.__init__ (self, source, delegate)
        
        assert event == self.CREATED or \
               event == self.DELETED or \
               event == self.CHANGED
        
        self.key   = key
        self.value = value
        self.event = event

    def get_id (self):
        return self.key

    def get_short_description (self):
        if self.event == self.CREATED:
            return _("Mozilla key '%s' set to '%s'") % (self.key, self.value)
        elif self.event == self.DELETED:
            return _("Mozilla key '%s' unset") % self.key
        elif self.event == self.CHANGED:
            return _("Mozilla key '%s' changed to '%s'") % (self.key, self.value)
        else:
            raise ValueError

gobject.type_register (MozillaChange)

class MozillaDelegate (userprofile.SourceDelegate):
    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, _("Files"), source, ".mozilla")
        self.source = source
        self.delegate = self
        self.pref_files = {}
        self.home_dir = util.get_home_dir ()
        if os.path.isfile(self.get_profiles_ini_path()):
            self.ini_file = FirefoxProfilesIni(self.get_profiles_ini_path())
        else:
            self.ini_file = None

    def get_full_path(self, path):
        return os.path.join(self.home_dir, path)        

    def get_rel_path(self, path):
        # XXX - isn't there a more elegant and robust way to do this?
        return os.path.normpath(path).split(os.path.normpath(self.home_dir))[1][1:]


    def get_profiles_ini_path(self):
        return self.get_full_path(ini_partial_path)

    def is_ini_file(self, path):
        ini_path_re = re.compile(ini_partial_path + "$")
        if ini_path_re.search(path):
            return True
        else:
            return False

    def is_prefs_file(self, path):
        if self.ini_file:
            ini_path = self.ini_file.get_full_path()
            ini_dir = os.path.dirname(ini_path)
            if path.startswith(ini_dir):
                for profile_dir in self.ini_file.get_profiles(True):
                    if path == os.path.join(profile_dir, "prefs.js"):
                        return True
                return False
            else:
                return False
        else:
            return False

    def handle_change (self, change):
        # XXX - jrd
        assert isinstance(change, filessource.FilesChange)
        path = self.get_full_path(change.get_id())
        if change.event == dirmonitor.CREATED:
            if self.is_ini_file(path):
                dprint("CREATED ini file: %s", path)
                if self.ini_file:
                    dwarn("ini file (%s) reports creation, but was already known", path)
                else:
                    self.ini_file = FirefoxProfilesIni(path)
                    self.ini_file.read()
                return True

            if self.is_prefs_file(path):
                dprint("CREATED prefs file: %s", path)
                if path in self.pref_files:
                    dwarn("prefs file (%s) reports creation, but was already known", path)
                else:
                    pref = JavascriptPrefsFile(path, self.source, self.delegate)
                    self.pref_files[path] = pref
                    pref.read()
                return True
            
            dprint("CREATED Ignored: %s", path)
            return True

        if change.event == dirmonitor.CHANGED:
            if self.is_ini_file(path):
                dprint("CHANGED ini file: %s", path)
                self.ini_file = FirefoxProfilesIni(path)
                self.ini_file.read()
                return True

            if self.is_prefs_file(path):
                dprint("CHANGED prefs file: %s", path)
                pref = self.pref_files.setdefault(path, JavascriptPrefsFile(path, self.source, self.delegate))
                pref.read()
                return True
            
            dprint("CHANGED Ignored: %s", path)
            return True

        if change.event == dirmonitor.DELETED:
            if self.is_ini_file(path):
                dprint("DELETED ini file: %s", path)
                if path == self.ini_file:
                    self.ini_file = None
                else:
                    dwarn("ini file (%s) reports deletion, but was not known ini (%s)", path, self.ini_file)
                return True

            if self.is_prefs_file(path):
                dprint("DELETED prefs file: %s", path)
                if path in self.pref_files:
                    del self.pref_files[path]
                return True
            
            dprint("DELETED Ignored: %s", path)
            return True

        raise ValueError


        return True

    def commit_change (self, change, mandatory = False):
        dprint ("Commiting (mandatory = %s) key = %s value = %s event = %s",
                mandatory, change.key, change.value, change.event)

        # XXX - jrd we need to mark here what gets written in sync_changes
        
        
    def sync_changes (self):
        """Ensure that all committed changes are saved to disk."""

        for pref in self.pref_files.values():
            ini = self.ini_file
            # XXX - this path stuff is a mess!
            pref_path = os.path.join(os.path.dirname(ini_partial_path), ini.get_default_profile().get_rel_path(), "sabayon-prefs.js")
            pref.write_pref_file(self.get_full_path(pref_path))
            self.source.storage.add (pref_path, self.home_dir, self.name)
            break;

    def apply (self):
        pass

def get_files_delegate (source):
    return MozillaDelegate (source)

#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------

# ------ Globals ------

# XXX - Warning: this regular expression is not perfectly robust
# the 1st parameter is expected to be a double quoted string without
# commas in it nor escaped double quotes. The parsing of the 2nd parameter
# should be robust. For our expected input it should be fine. Really
# robust parsing would require tokeninzing the expression.
pref_re = re.compile("user_pref\s*\(\s*\"([^,\"]+)\s*\"\s*,\s*(.+?)\)\s*;\s*$", re.MULTILINE)

# ------ Excpetions ------

class FileNotFoundError(Exception):
    def __init__(self, filename):
        self.filename = filename
    def __str__(self):
        return _("File Not Found (%s)") % self.filename
    
class BadIniFileError(Exception):
    def __init__(self, problem):
        self.problem = problem
    def __str__(self):
        return self.problem
    

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
        dprint("intersection = %s" % ",".join(self.intersection))
        dprint("only a = %s" % ",".join(self.only_a))
        dprint("only b = %s" % ",".join(self.only_b))
        dprint("equal = %s" % ",".join(self.equal))
        dprint("not equal = %s" % ",".join(self.not_equal))


# ------ Class JavascriptPrefsFile ------

class JavascriptPrefsFile:
    def __init__(self, path, source, delegate):
        self.path = path
        self.source = source
        self.delegate = delegate
        self.prefs = {}
        self.prev_prefs = {}


    def write_pref_file(self, pref_path):
        fd = open(pref_path, "w")
        fd.write('''
/*
 * Do not edit this file.
 * Created by %s, version %s
 */
 
''' % (config.PACKAGE, config.VERSION))

        # XXX - jrd
        type = 'user_pref'
        keys = self.prefs.keys()
        keys.sort()
        for key in keys:
            value = self.prefs[key]
            fd.write("%s(\"%s\", %s);\n" %
                     (type, key, value))

        fd.close()
        

    def read(self):
        self.prev_prefs = self.get_prefs()

        fd = open(self.path)
        self.filebuf = fd.read()
        fd.close()
        self.kill_comments()
        self.parse()

        cur_prefs = self.get_prefs()

        dc = DictCompare(self.prev_prefs, cur_prefs)
        dc.compare()
        cs = dc.get_change_set('a', 'b')
        dump_change_set(cs)

        _add = cs['add']
        _del = cs['del']
        _mod = cs['mod']

        def emit_changes(self, items, event):
            for key, value in items:
                self.source.emit_change(MozillaChange (self.source, self.delegate, key, value, event))

        emit_changes(self, _add.items (), MozillaChange.CREATED)
        emit_changes(self, _del.items (), MozillaChange.DELETED)
        emit_changes(self, _mod.items (), MozillaChange.CHANGED)

        self.prev_prefs = cur_prefs


    def kill_comments(self):
        slash_comment_re = re.compile("//.*$", re.MULTILINE)
        hash_comment_re = re.compile("#.*$", re.MULTILINE)
        c_comment_re = re.compile("/\*.*?\*/", re.MULTILINE | re.DOTALL)

        self.filebuf = slash_comment_re.sub("", self.filebuf)
        self.filebuf = hash_comment_re.sub("", self.filebuf)
        self.filebuf = c_comment_re.sub("", self.filebuf)

    def parse(self):
        start = 0;
        self.prefs = {}

        while 1:
            match = pref_re.search(self.filebuf, start)
            if match:
                key   = match.group(1)
                value = match.group(2)
                dprint("(%d:%d) key='%s' value='%s'" %
                       (match.start(), match.end(), key, value))
                self.prefs[key] = value
                start = match.end()
            else:
                break

    def get_prefs(self):
        return self.prefs.copy()

    def dump_prefs(self):
        keys = self.prefs.keys()
        keys.sort()
        for key in keys:
            dprint("%s=%s" % (key, self.prefs[key]))


# ------ Class FirefoxProfile ------

class FirefoxProfile:
    def __init__(self, section, dir):
        self.section = section
        self.dir = dir
        self.attrs = {}

    def set_attr(self, attr, value):
        self.attrs[attr] = value

    def get_attr(self, attr):
        return self.attrs[attr]

    def get_name(self):
        return self.get_attr("name")

    def get_default(self):
        return self.get_attr("default")

    def get_rel_path(self):
        return self.get_attr("path")

    def get_full_path(self):
        return os.path.join(self.dir, self.get_rel_path())
        


# ------ Class FirefoxProfilesIni ------

class FirefoxProfilesIni:
    (INI_STATE_UNKNOWN,
     INI_STATE_VALID,
     INI_STATE_NOT_FOUND,
     INI_STATE_PARSE_ERROR) = range(4)

    def __init__(self, path):
        self.state = self.INI_STATE_UNKNOWN
        self.default_profile = None
        self.profiles = {}
        self.ini = ConfigParser.ConfigParser()
        self.path = path
        self.dir = os.path.dirname(path)

    def get_full_path(self):
        return self.path

    def read(self):
        dprint("FirefoxProfilesIni.read() path = %s",
               self.path)
        self.profiles = {}

        try:
            if self.ini.read(self.path):
                self.state = self.INI_STATE_VALID
            else:
                self.state = self.INI_STATE_NOT_FOUND
        except ConfigParser.ParsingError, e:
            self.state = self.INI_STATE_PARSE_ERROR
        

        if self.state != self.INI_STATE_VALID:
            self.default_profile = None

        self.parse_sections()

    def parse_sections(self):
        profile_re = re.compile("^Profile(\d+)$")

        self.default_profile = None
        self.profiles = {}
        last_profile = None
        
        for section in self.ini.sections():
            dprint("parse_sections() section=%s", section)
            match = profile_re.match(section)
            if match:
                try:
                    default_profile = self.ini.get(section, "default")
                except ConfigParser.NoOptionError:
                    default_profile = None
                
                name = self.ini.get(section, "Name")
                if name in self.profiles:
                    raise BadIniFileError(_("duplicate name (%s) in section %s") %
                                          (name, section))
                profile = FirefoxProfile(section, self.dir)
                self.profiles[name] = profile
                for (key, value) in self.ini.items(section):
                    profile.set_attr(key, value)
                
                if default_profile:
                    if self.default_profile:
                        raise BadIniFileError(_("redundant default in section %s") %
                                              section)
                    self.default_profile = profile

                last_profile = profile

        if self.default_profile == None and len(self.profiles) == 1:
            # If there's only one profile, its the default even if it
            # doesn't have the Default=1 flag
            # Note: by default Firefox's auto-generated profile doesn't
            # have the Default= flag)
            self.default_profile = last_profile
            dprint("defaulting profile to the only choice")
            
        
    def get_default_profile(self):
        if not self.default_profile:
            raise BadIniFileError(_("no default profile"))
        return self.default_profile

    def get_profiles(self, as_full_path=False):
        if as_full_path:
            return [ profile.get_full_path()
                     for profile in self.profiles.values() ]
        else:
            return self.profiles.values()

# ------ Utility Functions ------

# XXX - this needs more logic to distinquish mozilla, firefox, versions, etc.
# basically its just hardcoded at the moment.
def GetProfileIniFile():
    filename = os.path.expanduser("~/%s" % ini_partial_path)

    # XXX - should caller thow error instead?
    if not os.path.exists(filename):
        raise FileNotFoundError(filename)

    return(filename)

def insert_prefs_into_file(path, prefs):
    (wfd, tmppath) = tempfile.mkstemp(dir=os.path.dirname(path))

    for line in open(path):
        wfd.write(line)

    for key, value in prefs.items():
        wfd.write("user_pref(\"%s\", %s);\n" % (key, value))

    wfd.close()
    os.rename(tmppath, path)

# XXX - this does not deal with comments
def remove_prefs_from_file(path, prefs):
    (wfd, tmppath) = tempfile.mkstemp(dir=os.path.dirname(path))

    for line in open(path):
        match = pref_re.search(line)
        if match:
            key = match.group(1)
            if type(prefs) is types.DictType:
                if not prefs.has_key(key):
                    wfd.write(line)
            elif type(prefs) is types.ListType:
                if not key in prefs:
                    wfd.write(line)
            else:
                raise ValueError
        else:
            wfd.write(line)

    wfd.close()
    os.rename(tmppath, path)


def dump_change_set(cs):
    _add = cs['add']
    _del = cs['del']
    _mod = cs['mod']

    if len(_add.keys()):
        dprint("Key/Values to ADD")
        for k in _add.keys():
            dprint("    %s=%s" % (k, _add[k]))

    if len(_del.keys()):
        dprint("Keys to DELETE")
        for k in _del.keys():
            dprint("    %s=%s" % (k, _del[k]))

    if len(_mod.keys()):
        dprint("Key/Values to Modify")
        for k in _mod.keys():
            dprint("    %s=%s" % (k, _mod[k]))

#-----------------------------------------------------------------------------

#
# Unit tests
#
def run_unit_tests ():
    test_prefs = {'foo':'"bar"', 'uno':'1'}

    dprint("In mozillaprofile tests")

    try:
        profile_ini_file = GetProfileIniFile()
    except FileNotFoundError, e:
        print _("No such profile ini file: %s") % e.filename
        return

    dprint("ini file = %s" % profile_ini_file)

    profiles_ini = FirefoxProfilesIni(profile_ini_file)
    profiles_ini.read()
    profiles_ini.parse_sections()
    default_path = profiles_ini.get_default_path()
    dprint("default_path = %s" % default_path)

    prefs_path = "%s/%s" % (default_path, "prefs.js")

    # make sure we're working with a clean file copy
    remove_prefs_from_file(prefs_path, test_prefs)

    pref = JavascriptPrefsFile(prefs_path)
    pref.open()
    pref.kill_comments()
    pref.parse()
    prev_prefs = pref.get_prefs()
    
    insert_prefs_into_file(prefs_path, test_prefs)

    pref = JavascriptPrefsFile(prefs_path)
    pref.open()
    pref.kill_comments()
    pref.parse()
    cur_prefs = pref.get_prefs()

    dc = DictCompare(prev_prefs, cur_prefs)
    dc.compare()

    cs = dc.get_change_set('a', 'b')
    dprint("a <-- b")
    dump_change_set(cs)

    dc = DictCompare(test_prefs, cs['add'])
    dc.compare()
    assert dc.is_equal() == True

    test_prefs['newkey'] = 'new'
    dc = DictCompare(test_prefs, cs['add'])
    dc.compare()
    assert dc.is_equal() == False

    del test_prefs['newkey']
    dc = DictCompare(test_prefs, cs['add'])
    dc.compare()
    assert dc.is_equal() == True

    test_prefs['uno'] = '2'
    dc = DictCompare(test_prefs, cs['add'])
    dc.compare()
    assert dc.is_equal() == False

    remove_prefs_from_file(prefs_path, test_prefs)


