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
import errno

class file_state:
    (UNKNOWN,
     VALID,
     NOT_FOUND,
     SYS_ERROR,
     PARSE_ERROR
     ) = range(5)


firefox_rel_path = ".mozilla/firefox"
profiles_ini_rel_path = os.path.join(firefox_rel_path, "profiles.ini")

def dprint(fmt, *args):
    util.debug_print(util.DEBUG_MOZILLASOURCE, fmt % args)

def dwarn(fmt, *args):
    print >> sys.stderr, "WARNING " + fmt % args

class MozillaChange(userprofile.ProfileChange):
    (
        CREATED,
        DELETED,
        CHANGED
    ) = range(3)
    
    def __init__ (self, source, delegate, type, key, value, event):
        userprofile.ProfileChange.__init__ (self, source, delegate)
        
        assert event == self.CREATED or \
               event == self.DELETED or \
               event == self.CHANGED
        
        self.type  = type
        self.key   = key
        self.value = value
        self.event = event
        self.attrs = {}

    def set_attr(self, attr, value):
        self.attrs[attr] = value

    def get_attr(self, attr):
        return self.attrs[attr]

    def get_type(self):
        return self.type

    def get_key(self):
        return self.key

    def get_value(self):
        return self.value

    def get_id(self):
        return self.key

    def get_short_description(self):
        if self.event == self.CREATED:
            return _("Mozilla key '%s' set to '%s'") % (self.key, self.value)
        elif self.event == self.DELETED:
            return _("Mozilla key '%s' unset") % self.key
        elif self.event == self.CHANGED:
            return _("Mozilla key '%s' changed to '%s'") % (self.key, self.value)
        else:
            raise ValueError

gobject.type_register(MozillaChange)

class MozillaDelegate(userprofile.SourceDelegate):
    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, _("Firefox"), source, ".mozilla")
        self.source = source
        self.delegate = self
        self.home_dir = util.get_home_dir()
        self.committed_prefs = {}
        self.committed_mandatory_prefs = {}
        self.ini_file = None
        self.load_profiles_ini()

    def get_full_path(self, path):
        return os.path.join(self.home_dir, path)        

    def get_profiles_ini_path(self):
        return self.get_full_path(profiles_ini_rel_path)

    def load_profiles_ini(self):
        if not self.ini_file:
            self.ini_file = FirefoxProfilesIni(self.home_dir, profiles_ini_rel_path)
        self.ini_file.read()

    def is_ini_file(self, rel_path):
        if rel_path == profiles_ini_rel_path:
            return True
        else:
            return False

    def is_profile_file(self, rel_path):
        if self.ini_file.is_valid():
            rel_dir = os.path.dirname(rel_path)
            for profile in self.ini_file.get_profiles():
                profile_rel_dir = profile.get_rel_dir()
                if rel_dir.startswith(profile_rel_dir):
                    return profile
            return None
        else:
            return None

    def handle_change(self, change):
        rel_path = change.get_id()
        #
        # INI File
        #
        if self.is_ini_file(rel_path):
            dprint("%s ini file: %s",
                   dirmonitor.event_to_string(change.event), rel_path)
            self.load_profiles_ini()

        #
        # Profile File
        #
        profile = self.is_profile_file(rel_path)
        if profile:
            dprint("%s profile file: %s",
                   dirmonitor.event_to_string(change.event), rel_path)

            # XXX - jrd, we shouldn't have to create a file just to get its type
            profile_file = profile.add_file(rel_path)
            profile_file_type = profile_file.get_type()

            if profile_file_type == FirefoxProfileFile.TYPE_PREFS:
                if change.event == dirmonitor.CREATED or \
                   change.event == dirmonitor.CHANGED:
                    if not isinstance(profile_file, JavascriptPrefsFile):
                        profile_file = profile.add_file(rel_path, JavascriptPrefsFile(self.home_dir, rel_path, self.source, self.delegate))
                    profile_file.read()
                    return True
                elif change.event == dirmonitor.DELETED:
                    pass
                else:
                    raise ValueError
            elif profile_file_type != FirefoxProfileFile.TYPE_UNKNOWN:
                if change.event == dirmonitor.CREATED or \
                   change.event == dirmonitor.CHANGED:
                    profile.add_file(rel_path)
                elif change.event == dirmonitor.DELETED:
                    profile.del_file(rel_path)
                else:
                    raise ValueError
            else:
                return True
                    
        #
        # Ignored Files
        #
        dprint("IGNORED: %s", rel_path)
        return True

    def commit_change(self, change, mandatory = False):
        dprint("Commiting (mandatory = %s) key = %s value = %s event = %s",
                mandatory, change.key, change.value, change.event)

        # XXX - jrd we need to mark here what gets written in sync_changes
        assert isinstance(change, MozillaChange)
        if mandatory:
            self.committed_mandatory_prefs[change.get_key()] = \
                JavascriptPreference(change.get_type(), change.get_key(), change.get_value())
        else:
            self.committed_prefs[change.get_key()] = \
                JavascriptPreference(change.get_type(), change.get_key(), change.get_value())
                

    def sync_changes(self):
        """Ensure that all committed changes are saved to disk."""

        dprint("sync_changes: home_dir = %s", self.home_dir)
        ini = self.ini_file
        if ini.is_valid():
            default_profile = ini.get_default_profile()
            pref_rel_dir = default_profile.get_rel_dir()
            dprint("sync_changes: default profile rel dir = %s", pref_rel_dir)


            self.source.storage.add(ini.get_rel_path(), self.home_dir, self.name,
                                    {"file_type" : FirefoxProfileFile.TYPE_PROFILE_INI})

            if len(self.committed_prefs) > 0:
                pref_rel_path = os.path.join(pref_rel_dir, "sabayon-firefox-prefs.js")
                pref_file = JavascriptPrefsFile(self.home_dir, pref_rel_path, self.source, self.delegate)
                pref_file.set_prefs(self.committed_prefs)
                pref_file.write()
                self.source.storage.add(pref_rel_path, self.home_dir, self.name,
                                         {"file_type" : FirefoxProfileFile.TYPE_PREFS,
                                          "mandatory"    : False})

            if len(self.committed_mandatory_prefs) > 0:
                pref_rel_path = os.path.join(pref_rel_dir, "sabayon-firefox-mandatory-prefs.js")
                pref_file = JavascriptPrefsFile(self.home_dir, pref_rel_path, self.source, self.delegate)
                pref_file.set_prefs(self.committed_mandatory_prefs)
                pref_file.write()
                self.source.storage.add(pref_rel_path, self.home_dir, self.name,
                                         {"file_type" : FirefoxProfileFile.TYPE_PREFS,
                                          "mandatory"    : True})

    def apply(self):
        ini_files = []
        pref_files = []
        bookmark_files = []
        other_files = []
        
        dprint("apply: home_dir = %s", self.home_dir)
        storage_contents = self.source.storage.list(self.name)

        for source, path in storage_contents:
            attributes = self.source.storage.get_attributes(path)
            file_type = attributes.get("file_type", None)
            if file_type != None:
                file_type = int(file_type)
            else:
                file_type = get_type_from_path(path)

            if file_type == FirefoxProfileFile.TYPE_PROFILE_INI:
                ini_files.append(path)
            elif file_type == FirefoxProfileFile.TYPE_PREFS:
                pref_files.append(path)
            elif file_type == FirefoxProfileFile.TYPE_BOOKMARK:
                bookmark_files.append(path)
            elif file_type == FirefoxProfileFile.TYPE_UNKNOWN:
                other_files.append(path)
            else:
                raise ValueError
            
        dprint("apply: ini_files=%s pref_files=%s bookmark_files=%s other_files=%s",
               ini_files, pref_files, bookmark_files, other_files)

        # Profiles.ini file must be done first, if the target does not
        # exist then extract it from the profile.
        # Parse the profiles.ini file to learn the target profiles
        self.load_profiles_ini()
        if not self.ini_file.is_valid():
            dprint("apply: no valid ini file, extracting %s", profiles_ini_rel_path)
            if profiles_ini_rel_path in ini_files:
                self.source.storage.extract(profiles_ini_rel_path, self.home_dir, True)
                self.load_profiles_ini()
            else:
                dprint("apply: but there isn't an ini file in the profile!")

        # Now merge the javascript pref files
        # XXX - iterate over all target profiles
        for profile in self.ini_file.get_profiles():
            dprint("apply: applying to profile %s", profile.attrs)
            profile_rel_dir = profile.get_rel_dir()
            target_pref_rel_path = os.path.join(profile_rel_dir, "prefs.js")
            target_pref = JavascriptPrefsFile(self.home_dir, target_pref_rel_path, self.source, self.delegate)
            target_pref.read()

            dprint("apply: target profile rel path = %s", target_pref_rel_path)
            for path in pref_files:
                attributes = self.source.storage.get_attributes(path)
                mandatory = attributes.get("mandatory", False)
                dprint("apply: applying src profile %s, mandatory=%s", path, mandatory)
                # XXX - should we delete this file after applying it?
                self.source.storage.extract(path, self.home_dir, True)
                # XXX - jrd, should this JavascriptPrefsFile have a source and delegate?
                apply_pref = JavascriptPrefsFile(self.home_dir, path, self.source, self.delegate)
                apply_pref.read()
                target_pref.merge(apply_pref, mandatory)

            target_pref.write()

        # Now merge the bookmarks
        for path in bookmark_files:
            # XXX - merge not implemented.
            pass

        # Finally extract any other file
        for path in other_files:
            attributes = self.source.storage.get_attributes(path)
            mandatory = attributes.get("mandatory", False)
            dprint("apply: extracting other file %s, mandatory=%s", path, mandatory)
            self.source.storage.extract(path, self.home_dir, mandatory)
            

def get_files_delegate(source):
    return MozillaDelegate(source)

#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------

# ------ Globals ------

# XXX - Warning: this regular expression is not perfectly robust
# the 1st parameter is expected to be a double quoted string without
# commas in it nor escaped double quotes. The parsing of the 2nd parameter
# should be robust. For our expected input it should be fine. Really
# robust parsing would require tokeninzing the expression.
pref_re = re.compile("(pref|user_pref|lock_pref)\s*\(\s*\"([^,\"]+)\s*\"\s*,\s*(.+?)\)\s*;\s*$", re.MULTILINE)

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


# ------ Class FirefoxProfileFile ------

class FirefoxProfileFile:
    (TYPE_UNKNOWN,
     TYPE_PROFILE_INI,
     TYPE_PREFS,
     TYPE_BOOKMARK
     ) = range(4)

    def __init__(self, rel_path):
        self.rel_path = rel_path
        self.attrs = {}
        self.file_type = get_type_from_path(rel_path)

    def type_to_string(self, type):
        if type == FirefoxProfileFile.TYPE_UNKNOWN:
            return "UNKNOWN"
        if type == FirefoxProfileFile.TYPE_PROFILE_INI:
            return "PROFILE_INI"
        if type == FirefoxProfileFile.TYPE_PREFS:
            return "PREFS"
        if type == FirefoxProfileFile.TYPE_BOOKMARK:
            return "BOOKMARK"
        return "?"

    def get_type(self):
        return self.file_type

# ------ Class JavascriptPreference ------

class JavascriptPreference:
    def __init__(self, type, key, value):
        self.type = type
        self.key = key
        self.value = value

    def __eq__(self, other):
        if self.type  == other.type and \
           self.key   == other.key  and \
           self.value == other.value:
            return True
        else:
            return False

    def get_type(self):
        return self.type

    def get_key(self):
        return self.key

    def get_value(self):
        return self.value

# ------ Class JavascriptPrefsFile ------

class JavascriptPrefsFile(FirefoxProfileFile):
    def __init__(self, home_dir, rel_path, source, delegate):
        FirefoxProfileFile.__init__(self, rel_path)
        self.file_state = file_state.UNKNOWN
        self.home_dir = home_dir
        self.source = source
        self.delegate = delegate
        self.prefs = {}
        self.prev_prefs = {}


    def get_full_path(self):
        return os.path.join(self.home_dir, self.rel_path)

    def get_file_state(self):
        return self.file_state

    def write(self, full_path=None):
        if not full_path:
            full_path = self.get_full_path()
        dir = os.path.dirname(full_path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        dprint("writing pref file (%s)", full_path)
        fd = open(full_path, "w")
        fd.write('''
/*
 * Do not edit this file.
 * Created by %s, version %s
 */
 
''' % (config.PACKAGE, config.VERSION))

        keys = self.prefs.keys()
        keys.sort()
        for key in keys:
            pref = self.prefs[key]
            fd.write("%s(\"%s\", %s);\n" %
                     (pref.get_type(), pref.get_key(), pref.get_value()))

        fd.close()
        

    def merge(self, src, mandatory):
        for src_pref in src.prefs.values():
            src_key = src_pref.get_key()
            if not self.prefs.has_key(src_key) or mandatory:
                # XXX - should this just be a copy?
                self.prefs[src_key] = JavascriptPreference(src_pref.get_type(),
                                                           src_pref.get_key(),
                                                           src_pref.get_value())
                

    def read(self):
        self.prev_prefs = self.get_prefs()

        dprint("read profile prefs (%s)", self.get_full_path())
        self.file_state = file_state.UNKNOWN
        try:
            fd = open(self.get_full_path())
        except IOError, e:
            if e.errno == errno.ENOENT:
                self.file_state = file_state.NOT_FOUND
                return
            else:
                self.file_state = file_state.SYS_ERROR
                raise

        self.filebuf = fd.read()
        fd.close()
        self.file_state = file_state.VALID

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
            for key, pref in items:
                self.source.emit_change(
                    MozillaChange(self.source, self.delegate,
                                  pref.get_type(), pref.get_key(), pref.get_value(), event))

        emit_changes(self, _add.items(), MozillaChange.CREATED)
        emit_changes(self, _del.items(), MozillaChange.DELETED)
        emit_changes(self, _mod.items(), MozillaChange.CHANGED)

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
                type  = match.group(1)
                key   = match.group(2)
                value = match.group(3)
                dprint("(%d:%d) key='%s' value='%s'" %
                       (match.start(), match.end(), key, value))
                self.prefs[key] = JavascriptPreference(type, key, value)
                start = match.end()
            else:
                break

    def set_prefs(self, prefs):
        self.prefs = prefs.copy()

    def get_prefs(self):
        return self.prefs.copy()

    def dump_prefs(self):
        keys = self.prefs.keys()
        keys.sort()
        for key in keys:
            dprint("%s=%s" % (key, self.prefs[key]))


# ------ Class FirefoxProfile ------

class FirefoxProfile:
    def __init__(self, section, rel_dir):
        self.section = section
        self.rel_dir = rel_dir
        self.attrs = {}
        self.files = {}

    def set_attr(self, attr, value):
        self.attrs[attr] = value

    def get_attr(self, attr):
        return self.attrs[attr]

    def get_name(self):
        return self.get_attr("name")

    def get_default(self):
        return self.get_attr("default")

    def get_rel_dir(self):
        return os.path.join(self.rel_dir, self.get_dir())

    def get_dir(self):
        return self.get_attr("path")

    def add_file(self, rel_path, object=None):
        # XXX - jrd, passing object in is ugly & awkward, find more elegant solution
        if not object:
            object = FirefoxProfileFile(rel_path)
            file = self.files.setdefault(rel_path, object)
        else:
            file = object
            file = self.files[rel_path] = object
        return file

    def del_file(self, rel_path):
        if rel_path in self.files:
            del self.files[rel_path]

    def get_files_of_type(self, type):
        return [ file
                 for file in self.files.values() if file.get_type() == type ]


# ------ Class FirefoxProfilesIni ------

class FirefoxProfilesIni:
    def __init__(self, home_dir, rel_path):
        self.file_state = file_state.UNKNOWN
        self.default_profile = None
        self.profiles = {}
        self.ini = ConfigParser.ConfigParser()
        self.home_dir = home_dir
        self.rel_path = rel_path
        self.rel_dir = os.path.dirname(rel_path)

    def is_valid(self):
        return self.file_state == file_state.VALID

    def get_full_path(self, path):
        return os.path.join(self.home_dir, path)        

    def get_rel_dir(self):
        return self.rel_dir

    def get_rel_path(self):
        return self.rel_path

    def get_file_state(self):
        return self.file_state

    def read(self):
        dprint("FirefoxProfilesIni.read() path = %s",
               self.get_full_path(self.rel_path))
        self.profiles = {}

        try:
            if self.ini.read(self.get_full_path(self.rel_path)):
                self.file_state = file_state.VALID
            else:
                self.file_state = file_state.NOT_FOUND
        except ConfigParser.ParsingError, e:
            self.file_state = file_state.PARSE_ERROR
        

        dprint("FirefoxProfilesIni: after read, state = %s", self.file_state)
        if self.file_state != file_state.VALID:
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
                    raise BadIniFileError(_("duplicate name(%s) in section %s") %
                                          (name, section))
                profile = FirefoxProfile(section, self.rel_dir)
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

    def get_profiles(self, as_rel_dir=False):
        if as_rel_dir:
            return [ profile.get_rel_dir()
                     for profile in self.profiles.values() ]
        else:
            return self.profiles.values()

# ------ Utility Functions ------

def get_type_from_path(rel_path):
    basename = os.path.basename(rel_path)
    
    if basename == "prefs.js":
        return FirefoxProfileFile.TYPE_PREFS
    elif basename == "bookmarks.html":
        return FirefoxProfileFile.TYPE_BOOKMARK
    else:
        return FirefoxProfileFile.TYPE_UNKNOWN


# XXX - this needs more logic to distinquish mozilla, firefox, versions, etc.
# basically its just hardcoded at the moment.
def GetProfileIniFile():
    filename = os.path.expanduser("~/%s" % profiles_ini_rel_path)

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
            key = match.group(2)
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
def run_unit_tests():
    test_prefs = {'foo':'"bar"', 'uno':'1'}

    dprint("In mozillaprofile tests")

    try:
        profile_ini_file = GetProfileIniFile()
    except FileNotFoundError, e:
        print _("No such profile ini file: %s") % e.filename
        return

    dprint("ini file = %s" % profile_ini_file)

    profiles_ini = FirefoxProfilesIni(os.path.expanduser("~"), profile_ini_file)
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


