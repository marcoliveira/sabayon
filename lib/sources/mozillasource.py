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
import exceptions, sys, os.path, ConfigParser, re, cPickle
import tempfile, types
import traceback
import errno

try:
    import util
    import config
    import userprofile
    import dirmonitor
    import mozilla_bookmarks
except:
    from sabayon import util
    from sabayon import config
    from sabayon import userprofile
    from sabayon import dirmonitor
    from sabayon import mozilla_bookmarks

class file_state:
    (UNKNOWN,
     VALID,
     NOT_FOUND,
     SYS_ERROR,
     PARSE_ERROR
     ) = range(5)


firefox_rel_path = ".mozilla/firefox"
profiles_ini_rel_path = os.path.join(firefox_rel_path, "profiles.ini")
sabayon_pref_rel_path = os.path.join(firefox_rel_path, "sabayon-prefs.js")
sabayon_mandatory_pref_rel_path = os.path.join(firefox_rel_path, "sabayon-mandatory-prefs.js")

LOG_OPERATION           = 0x00001
LOG_CHANGE              = 0x00002
LOG_IGNORED_CHANGE      = 0x00004
LOG_APPLY               = 0x00008
LOG_SYNC                = 0x00010
LOG_PARSE               = 0x00020
LOG_PREF                = 0x00040
LOG_FILE_CONTENTS       = 0x00080
LOG_DATA                = 0x00100
LOG_VERBOSE             = 0x10000

def dprint(mask, fmt, *args):
    util.debug_print(util.DEBUG_MOZILLASOURCE, fmt % args, mask)

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
        dprint(LOG_OPERATION, "Delegate construction")
        userprofile.SourceDelegate.__init__ (self, _("Firefox"), source, ".mozilla")
        self.source = source
        self.delegate = self
        self.home_dir = util.get_home_dir()
        self.committed_prefs = {}
        self.committed_mandatory_prefs = {}
        self.committed_bookmarks = {}
        self.committed_mandatory_bookmarks = {}
        self.ini_file = None

    def get_full_path(self, path):
        return os.path.join(self.home_dir, path)        

    def get_profiles_ini_path(self):
        return self.get_full_path(profiles_ini_rel_path)

    def load_profiles_ini(self):
        if not self.ini_file:
            self.ini_file = FirefoxProfilesIni(self.home_dir, profiles_ini_rel_path)
        self.ini_file.read()

    def load_profiles(self):
        if self.ini_file:
            self.ini_file.load_profiles()

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
            dprint(LOG_CHANGE, "%s ini file: %s",
                   dirmonitor.event_to_string(change.event), rel_path)
            self.load_profiles_ini()

        #
        # Profile File
        #
        profile = self.is_profile_file(rel_path)
        if profile:
            dprint(LOG_CHANGE, "%s profile file: %s",
                   dirmonitor.event_to_string(change.event), rel_path)

            profile_file = profile.add_file(rel_path)
            profile_file_type = profile_file.get_type()

            if profile_file_type == FirefoxProfileFile.TYPE_PREFS:
                assert isinstance(profile_file, JavascriptPrefsFile)
                if change.event == dirmonitor.CREATED or \
                   change.event == dirmonitor.CHANGED:
                    cat_file(profile_file.get_full_path())
                    profile_file.read()
                    profile_file.emit_changes(self.source, self.delegate)
                    return True
                elif change.event == dirmonitor.DELETED:
                    # XXX - what to do here?
                    pass
                else:
                    raise ValueError
            elif profile_file_type == FirefoxProfileFile.TYPE_BOOKMARK:
                assert isinstance(profile_file, BookmarksFile)
                if change.event == dirmonitor.CREATED or \
                   change.event == dirmonitor.CHANGED:
                    profile_file.read()
                    profile_file.emit_changes(self.source, self.delegate)
                    return True
                elif change.event == dirmonitor.DELETED:
                    # XXX - what to do here?
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
        dprint(LOG_IGNORED_CHANGE, "IGNORED: %s", rel_path)
        return True

    def commit_change(self, change, mandatory = False):
        if isinstance(change, MozillaChange):
            dprint(LOG_CHANGE, "Commiting preference (mandatory = %s) key = %s value = %s event = %s",
                   mandatory, change.key, change.value, change.event)

            if mandatory:
                self.committed_mandatory_prefs[change.get_key()] = \
                    JavascriptPreference(change.get_type(), change.get_key(), change.get_value())
            else:
                self.committed_prefs[change.get_key()] = \
                    JavascriptPreference(change.get_type(), change.get_key(), change.get_value())
        elif isinstance(change, BookmarkChange):
            bookmark_path = change.get_bookmark_path()
            url = change.get_url()

            if url:
                object = mozilla_bookmarks.Bookmark(bookmark_path, url)
            else:
                object = mozilla_bookmarks.BookmarkFolder(bookmark_path, None)

            dprint(LOG_CHANGE, "Commiting bookmark (mandatory = %s) path = %s url = %s event = %s",
                   mandatory, bookmark_path, url, change.event)

            if mandatory:
                self.committed_mandatory_bookmarks[get_bookmark_path] = object
            else:
                self.committed_bookmarks[bookmark_path] = object
                

    def start_monitoring (self):
        """Start monitoring for configuration changes."""
        # Read all files we are going to monitor so that when a change is
        # reported we have a "before" state to compare to and thus derive
        # what is different.
        dprint(LOG_OPERATION, "start_monitoring:")
        self.load_profiles_ini()
        self.load_profiles()

    def stop_monitoring (self):
        """Stop monitoring for configuration changes."""
        dprint(LOG_OPERATION, "stop_monitoring:")

    def sync_changes(self):
        """Ensure that all committed changes are saved to disk."""

        dprint(LOG_SYNC, "sync_changes: home_dir = %s", self.home_dir)
        ini = self.ini_file
        if ini.is_valid():
            default_profile = ini.get_default_profile()

            self.source.storage.add(ini.get_rel_path(), self.home_dir, self.name,
                                    {"file_type" : FirefoxProfileFile.TYPE_PROFILE_INI})

            if len(self.committed_prefs) > 0:
                pref_rel_path = sabayon_pref_rel_path
                dprint(LOG_SYNC, "sync_changes: storing committed_prefs to %s", pref_rel_path)
                pref_file = JavascriptPrefsFile(self.home_dir, pref_rel_path)
                pref_file.set_prefs(self.committed_prefs)
                pref_file.write()
                self.source.storage.add(pref_rel_path, self.home_dir, self.name,
                                         {"file_type" : FirefoxProfileFile.TYPE_PREFS,
                                          "mandatory"    : False})

            if len(self.committed_mandatory_prefs) > 0:
                pref_rel_path = sabayon_mandatory_pref_rel_path
                dprint(LOG_SYNC, "sync_changes: storing mandatory committed_prefs to %s", pref_rel_path)
                pref_file = JavascriptPrefsFile(self.home_dir, pref_rel_path)
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
        
        dprint(LOG_APPLY, "apply: home_dir = %s", self.home_dir)
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
            
        dprint(LOG_APPLY, "apply: ini_files=%s pref_files=%s bookmark_files=%s other_files=%s",
               ini_files, pref_files, bookmark_files, other_files)

        # Profiles.ini file must be done first, if the target does not
        # exist then extract it from the profile.
        # Parse the profiles.ini file to learn the target profiles
        self.load_profiles_ini()
        if not self.ini_file.is_valid():
            dprint(LOG_APPLY, "apply: no valid ini file, extracting %s", profiles_ini_rel_path)
            if profiles_ini_rel_path in ini_files:
                self.source.storage.extract(profiles_ini_rel_path, self.home_dir, True)
                self.load_profiles_ini()
            else:
                dprint(LOG_APPLY, "apply: but there isn't an ini file in the profile!")

        if sabayon_pref_rel_path in pref_files:
            dprint(LOG_APPLY, "extracting %s" % sabayon_pref_rel_path)
            self.source.storage.extract(sabayon_pref_rel_path, self.home_dir, True)
            apply_pref = JavascriptPrefsFile(self.home_dir, path)
            apply_pref.read()
        else:
            apply_pref = None

        if sabayon_mandatory_pref_rel_path in pref_files:
            dprint(LOG_APPLY, ">>> extracting %s" % sabayon_mandatory_pref_rel_path)
            self.source.storage.extract(sabayon_mandatory_pref_rel_path, self.home_dir, True)
            mandatory_apply_pref = JavascriptPrefsFile(self.home_dir, path)
            mandatory_apply_pref.read()
        else:
            mandatory_apply_pref = None

        # Now merge the javascript pref files
        # XXX - iterate over all target profiles
        for profile in self.ini_file.get_profiles():
            dprint(LOG_APPLY, "apply: applying to profile %s", profile.attrs)
            profile_rel_dir = profile.get_rel_dir()
            target_pref_rel_path = os.path.join(profile_rel_dir, "prefs.js")
            target_pref = JavascriptPrefsFile(self.home_dir, target_pref_rel_path)
            target_pref.read()

            if apply_pref:
                mandatory = False
                dprint(LOG_APPLY, "apply: applying src profile %s to target profile %s, mandatory=%s",
                       sabayon_pref_rel_path, target_pref_rel_path, mandatory)
                target_pref.merge(apply_pref, mandatory)

            if mandatory_apply_pref:
                mandatory = True
                dprint(LOG_APPLY, "apply: applying src profile %s to target profile %s, mandatory=%s",
                       sabayon_pref_rel_path, target_pref_rel_path, mandatory)
                target_pref.merge(mandatory_apply_pref, mandatory)

            if apply_pref or mandatory_apply_pref:
                target_pref.write()

        # Now merge the bookmarks
        for path in bookmark_files:
            # XXX - merge not implemented.
            pass

        # Finally extract any other file
        for path in other_files:
            attributes = self.source.storage.get_attributes(path)
            mandatory = attributes.get("mandatory", False)
            dprint(LOG_APPLY, "apply: extracting other file %s, mandatory=%s", path, mandatory)
            self.source.storage.extract(path, self.home_dir, mandatory)
            
        dprint(LOG_APPLY, "apply: finished")

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
    

# ------ Class FirefoxProfileFile ------

class FirefoxProfileFile:
    (TYPE_UNKNOWN,
     TYPE_PROFILE_INI,
     TYPE_PREFS,
     TYPE_BOOKMARK
     ) = range(4)

    def __init__(self, home_dir, rel_path):
        self.home_dir = home_dir
        self.rel_path = rel_path
        self.attrs = {}
        self.file_type = get_type_from_path(rel_path)

    def get_full_path(self):
        return os.path.join(self.home_dir, self.rel_path)

    def get_rel_path(self):
        return self.rel_path

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
    def __init__(self, home_dir, rel_path):
        dprint(LOG_OPERATION, "JavascriptPrefsFile: created (%s)", rel_path)
        FirefoxProfileFile.__init__(self, home_dir, rel_path)
        self.file_state = file_state.UNKNOWN
        self.prefs = {}
        self.prev_prefs = {}

    def get_file_state(self):
        return self.file_state

    def write(self, full_path=None):
        if not full_path:
            full_path = self.get_full_path()
        dir = os.path.dirname(full_path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        dprint(LOG_OPERATION, "JavascriptPrefsFile: writing file (%s)", full_path)
        fd = open(full_path, "w")
        fd.write('''
# Mozilla User Preferences

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

        dprint(LOG_OPERATION, "read profile prefs (%s)", self.get_full_path())
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


    def emit_changes(self, source, delegate):
        cur_prefs = self.get_prefs()

        dc = util.DictCompare(self.prev_prefs, cur_prefs)
        dc.compare()
        cs = dc.get_change_set('a', 'b')

        _add = cs['add']
        _del = cs['del']
        _mod = cs['mod']

        def emit_changes(items, event):
            for key, pref in items:
                source.emit_change(
                    MozillaChange(source, delegate,
                                  pref.get_type(), pref.get_key(), pref.get_value(), event))

        emit_changes(_add.items(), MozillaChange.CREATED)
        emit_changes(_del.items(), MozillaChange.DELETED)
        emit_changes(_mod.items(), MozillaChange.CHANGED)

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
                dprint(LOG_PARSE, "(%d:%d) key='%s' value='%s'" %
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
            dprint(LOG_, "%s=%s" % (key, self.prefs[key]))


# ------ Class FirefoxProfile ------

class FirefoxProfile:
    def __init__(self, section, home_dir, rel_dir):
        self.section = section
        self.home_dir = home_dir
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

    def add_file(self, rel_path):
        object = self.files.get(rel_path, None)
        if object:
            return(object)


        file_type = get_type_from_path(rel_path)

        if file_type == FirefoxProfileFile.TYPE_PREFS:
            object = JavascriptPrefsFile(self.home_dir, rel_path)
        elif file_type == FirefoxProfileFile.TYPE_BOOKMARK:
            object = BookmarksFile(self.home_dir, rel_path)
        else:
            object = FirefoxProfileFile(self.home_dir, rel_path)
        self.files[rel_path] = object
        return object

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

    def load_profiles(self):
        dprint(LOG_OPERATION, "FirefoxProfilesIni.load_profiles()")
        for profile in self.get_profiles():
            profile_rel_dir = profile.get_rel_dir()

            pref_rel_path = os.path.join(profile_rel_dir, "prefs.js")
            dprint(LOG_OPERATION, "FirefoxProfilesIni.load_profiles() pref=%s", pref_rel_path)
            profile_file = profile.add_file(pref_rel_path)
            profile_file.read()

            bookmark_rel_path = os.path.join(profile_rel_dir, "bookmarks.html")
            dprint(LOG_OPERATION, "FirefoxProfilesIni.load_profiles() bookmark=%s", bookmark_rel_path)
            profile_file = profile.add_file(bookmark_rel_path)
            profile_file.read()



    def read(self):
        dprint(LOG_OPERATION, "FirefoxProfilesIni.read() path = %s",
               self.get_full_path(self.rel_path))
        self.profiles = {}

        try:
            if self.ini.read(self.get_full_path(self.rel_path)):
                self.file_state = file_state.VALID
            else:
                self.file_state = file_state.NOT_FOUND
        except ConfigParser.ParsingError, e:
            self.file_state = file_state.PARSE_ERROR
        

        dprint(LOG_PARSE, "FirefoxProfilesIni: after read, state = %s", self.file_state)
        if self.file_state != file_state.VALID:
            self.default_profile = None

        self.parse_sections()

    def parse_sections(self):
        profile_re = re.compile("^Profile(\d+)$")

        self.default_profile = None
        self.profiles = {}
        last_profile = None
        
        for section in self.ini.sections():
            dprint(LOG_PARSE, "parse_sections() section=%s", section)
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
                profile = FirefoxProfile(section, self.home_dir, self.rel_dir)
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
            dprint(LOG_OPERATION, "defaulting profile to the only choice")
            
        
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

# ------ Class BookmarkChange ------

class BookmarkChange(userprofile.ProfileChange):
    (
        CREATED,
        DELETED,
        CHANGED
    ) = range(3)
    
    def __init__ (self, source, delegate, bookmark_path, url, event):
        userprofile.ProfileChange.__init__ (self, source, delegate)
        
        assert event == self.CREATED or \
               event == self.DELETED or \
               event == self.CHANGED
        
        self.bookmark_path   = bookmark_path
        self.url = url
        self.event = event
        self.attrs = {}

    def set_attr(self, attr, value):
        self.attrs[attr] = value

    def get_attr(self, attr):
        return self.attrs[attr]

    def get_bookmark_path(self):
        return self.bookmark_path

    def get_url(self):
        return self.url

    def get_id(self):
        return self.bookmark_path

    def get_short_description(self):
        url = self.get_url()
        bookmark_path = self.get_bookmark_path()
        
        if self.event == self.CREATED:
            if url:
                return _("Mozilla bookmark created '%s' -> '%s'") % (bookmark_path, url)
            else:
                return _("Mozilla bookmark folder created '%s'") % (bookmark_path)
        elif self.event == self.DELETED:
            if url:
                return _("Mozilla bookmark deleted '%s'") % (bookmark_path)
            else:
                return _("Mozilla bookmark folder deleted '%s'") % (bookmark_path)
        elif self.event == self.CHANGED:
            if url:
                return _("Mozilla bookmark changed '%s' '%s'") % (bookmark_path, url)
            else:
                return _("Mozilla bookmark folder changed '%s'") % (bookmark_path)
                
        else:
            raise ValueError

gobject.type_register(BookmarkChange)

# ------ Class BookmarksFile ------

class BookmarksFile(FirefoxProfileFile):
    def __init__(self, home_dir, rel_path):
        dprint(LOG_OPERATION, "BookmarksFile: created (%s)", rel_path)
        FirefoxProfileFile.__init__(self, home_dir, rel_path)
        self.parser = mozilla_bookmarks.BookmarkHTMLParser()
        self.root = mozilla_bookmarks.BookmarkFolder("Null", None)
        self.parser.set_root(self.root)
        self.prev_root = self.parser.get_root()
        self.file_state = file_state.UNKNOWN
        self.bookmark_separator = "/"

    def get_folders(self):
        return self.root

    def read(self):
        self.prev_root = self.parser.get_root()
        self.root = mozilla_bookmarks.BookmarkFolder("Null", None)
        self.parser.set_root(self.root)
        self.file_state = file_state.UNKNOWN
        full_path = self.get_full_path()
        dprint(LOG_OPERATION, "BookmarksFile: read (%s)", full_path)
        try:
            fd = open(full_path)
        except IOError, e:
            if e.errno == errno.ENOENT:
                self.file_state = file_state.NOT_FOUND
                return
            else:
                self.file_state = file_state.SYS_ERROR
                raise

        self.file_state = file_state.VALID
        self.parser.feed(fd.read())
        self.parser.close()
        self.root = self.parser.get_root()
        
    def convert_to_dict(self, root):
        result = {}

        def visit(entry, type, path, data):
            if type == mozilla_bookmarks.TYPE_BOOKMARK:
                bookmark_path = entry.path_as_names(self.bookmark_separator)
                bookmark_url = entry.url()
                result[bookmark_path] = bookmark_url
            elif type == mozilla_bookmarks.TYPE_FOLDER:
                folder_path = entry.path_as_names(self.bookmark_separator)
                result[folder_path] = None

        root.traverse(visit)
        return result
    
    def emit_changes(self, source, delegate):
        prev_dict = self.convert_to_dict(self.prev_root)
        cur_dict  = self.convert_to_dict(self.root)

        dc = util.DictCompare(prev_dict, cur_dict)
        dc.compare()
        cs = dc.get_change_set('a', 'b')

        _add = cs['add']
        _del = cs['del']
        _mod = cs['mod']

        def emit_changes(items, event):
            for bookmark_path, bookmark_url in items:
                source.emit_change(
                    BookmarkChange(source, delegate,
                                  bookmark_path, bookmark_url, event))

        emit_changes(_add.items(), BookmarkChange.CREATED)
        emit_changes(_del.items(), BookmarkChange.DELETED)
        emit_changes(_mod.items(), BookmarkChange.CHANGED)


# ------ Utility Functions ------

def get_type_from_path(rel_path):
    basename = os.path.basename(rel_path)
    
    if basename == "prefs.js":
        return FirefoxProfileFile.TYPE_PREFS
    elif basename == "bookmarks.html":
        return FirefoxProfileFile.TYPE_BOOKMARK
    else:
        return FirefoxProfileFile.TYPE_UNKNOWN

def cat_file(path):
    if os.path.isfile(path):
        dprint(LOG_FILE_CONTENTS, "==== %s ====" % path)
        for line in open(path):
            dprint(LOG_FILE_CONTENTS, line.rstrip())
    else:
        dprint(LOG_FILE_CONTENTS, "WARNING, does not exist ==== %s ====" % path)



#-----------------------------------------------------------------------------

#
# Unit tests
#
def run_unit_tests():
    test_prefs = {'foo':'"bar"', 'uno':'1'}

    dprint(LOG_OPERATION, "In mozillaprofile tests")



