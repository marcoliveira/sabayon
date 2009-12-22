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

import sys
import string
import pwd
import grp
import os
import libxml2
import config
import util
import cache
import random
import socket
import debuglog

#
# LDAP should be a soft dependency.
#

try:
    import ldap
    has_ldap = True;
except ImportError:
    has_ldap = False;

#
# Default empty config.
#
defaultConf="""<profiles>
  <default profile=""/>
</profiles>"""

# make sure to initialize the cache first
# this will make sure we can handle disconnection
# and initialize libxml2 environment
cache.initialize()

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_USER_DB, fmt % args)

def get_setting (node, setting, default = None, convert_to = str):
    a = node.hasProp(setting)
    if a:
        try:
            return convert_to (a.content)
        except:
            np = node.nodePath()
            # Translators: You may move the "%(setting)s" and "%(np)s" items as you wish, but
            # do not change the way they are written.  The intended string is
            # something like "invalid type for setting blah in /ldap/path/to/blah"
            raise SystemDatabaseException(_("invalid type for setting %(setting)s in %(np)s") % { "setting": setting,
                                                                                                "np": np })
    return default

def expand_string (string, attrs):
    res = ""
    i = 0
    while i < len(string):
        c = string[i]
        i = i + 1
        if c == "%":
            if i < len(string):
                c = string[i]
                if c != "%":
                    if c in attrs:
                        c = attrs[c]
                i = i + 1
        res = res + c
    return res


class SystemDatabaseException (Exception):
    pass

class SystemDatabase(object):
    """An encapsulation of the database which maintains an
    association between users and profiles.

    This database is stored by default in
    $(sysconfdir)/desktop-profiles/users.xml and contains a
    list of users and the profile associated with each of
    those users.

    A profile can be reference by either its name (in which case
    the profile is stored at /etc/desktop-profiles/$(name).zip),
    an absolute path or a http/file URL.
    """
    def __init__ (self, db_file = None):
        """Create a SystemDatabase object.

        @db_file: a mandatory path which specifes the location
        of the database file. If only a file is specified, the
        directory /etc/desktop-profiles is used.
        """
        if db_file is None:
            raise SystemDatabaseException(_("No database file provided"))
        elif db_file[0] != '/':
            file = os.path.join (config.PROFILESDIR, db_file)
        else:
            file = db_file
        self.file = file
        self.xmlquery = None
        self.nodes = None        # nodes from the XML file for LDAP usage.
        self.modified = 0
        dprint("New UserDatabase(%s) object\n" % self.file)

        try:
            self.doc = libxml2.readFile(file, None, libxml2.XML_PARSE_NOBLANKS)
            # Process XInclude statements
            self.doc.xincludeProcess()
        except:
            # TODO add fallback to last good database
            dprint("failed to parse %s falling back to default conf\n" %
                   self.file)
            self.doc = None
        if self.doc == None:
            self.doc = libxml2.readMemory(defaultConf, len(defaultConf),
                                          None, None,
                                          libxml2.XML_PARSE_NOBLANKS)

    def __del__ (self):
        if self.doc != None:
            self.doc.freeDoc()

    def __profile_name_to_location (self, profile, node):
        if not profile:
            return None

        uri = self.__ldap_query ("locationmap", {"p":profile, "h":socket.getfqdn()})
        if uri:
            return uri

        # do the necessary URI escaping of the profile name if needed
        orig_profile = profile
        try:
            tmp = parseURI(profile)
        except:
            profile = libxml2.URIEscapeStr(profile, "/:")

        # if there is a base on the node, then use 
        if node != None:
            try:
                base = node.getBase(None)
                if base != None and base != "" and \
                   base != self.file:
                    # URI composition from the base
                    ret = libxml2.buildURI(profile, base)
                    if ret[0] == '/':
                        ret = libxml2.URIUnescapeString(ret, len(ret), None)
                    dprint("Converted profile name '%s' to location '%s'\n",
                           orig_profile, ret)
                    return ret
            except:
                pass
        try:
            uri = libxml2.parseURI(profile);
            if uri.scheme() is None:
                # it is a file path
                if profile[0] != '/':
                    profile = os.path.join (config.PROFILESDIR, profile)
                if profile[-4:] != ".zip":
                    profile = profile + ".zip"
            else:
                # TODO need to make a local copy or use the local copy
                profile = profile
        except:
            # we really expect an URI there
            profile = None

        if profile[0] == '/':
            profile = libxml2.URIUnescapeString(profile, len(profile), None)
        dprint("Converted profile name '%s' to location '%s'\n",
               orig_profile, profile)
        return profile

    def __open_ldap (self):
        ldap_node = self.nodes[0]

        server = get_setting (ldap_node, "server", "localhost")
        port = get_setting (ldap_node, "port", ldap.PORT, int)

        l = ldap.open (server, port)
        
        l.protocol_version = get_setting (ldap_node, "version", ldap.VERSION3, int)
        l.timeout =  get_setting (ldap_node, "timeout", 10, int)
        
        bind_dn = get_setting (ldap_node, "bind_dn", "")
        bind_pw = get_setting (ldap_node, "bind_pw", "")
        if bind_dn != "":
            l.simple_bind (bind_dn, bind_pw)
        
        return l

    def __ldap_query (self, map, replace):
        global has_ldap
        if not has_ldap:
            return None
        if not self.nodes:
            self.nodes = self.doc.xpathEval ("/profiles/ldap/" + map)
            if len (self.nodes) == 0:
                has_ldap = False        # No LDAP nodes in the xml file.
                return None
        map_node = self.nodes[0]
        
        l = self.__open_ldap ()
        if not l:
            return None
        
        search_base = get_setting (map_node, "search_base")
        query_filter = get_setting (map_node, "query_filter")
        result_attribute = get_setting (map_node, "result_attribute")
        scope = get_setting (map_node, "scope", "sub")
        multiple_result = get_setting (map_node, "multiple_result", "first")

        if search_base == None:
            raise SystemDatabaseException(_("No LDAP search base specified for %s" % map))
            
        if query_filter == None:
            raise SystemDatabaseException(_("No LDAP query filter specified for %s" % map))
            
        if result_attribute == None:
            raise SystemDatabaseException(_("No LDAP result attribute specified for %s" % map))

        if scope == "sub":
            scope = ldap.SCOPE_SUBTREE
        elif scope == "base":
            scope = ldap.SCOPE_BASE
        elif scope == "one":
            scope = ldap.SCOPE_ONELEVEL
        else:
            raise SystemDatabaseException(_("LDAP Scope must be one of: ") + "sub, base, one")
        
        query_filter = expand_string (query_filter, replace)
        search_base = expand_string (search_base, replace)

        results = l.search_s (search_base, scope, query_filter, [result_attribute])
        
        if len (results) == 0:
            return None

        (dn, attrs) = results[0]
        if not result_attribute in attrs:
            return None
        vals = attrs[result_attribute]

        if multiple_result == "first":
            val = vals[0]
        elif multiple_result == "random":
            val = vals[random.randint(0, len(vals)-1)]
        else:
            raise SystemDatabaseException(_("multiple_result must be one of: ") + "first, random")

        l.unbind ()
        
        return val


    def get_default_profile (self, profile_location = True):
        """Look up the default profile.

        @profile_location: whether the profile location should
        be returned

        Return value: the location of the default profile, which
        should be in a suitable form for constructing a ProfileStorage
        object, or the default profile name if @profile_location is
        False.
        """
        default = None
        try:
            default = self.doc.xpathEval("/profiles/default")[0]
            profile = default.prop("profile")
        except:
            profile = None

        if not profile_location:
            return profile
        
        return self.__profile_name_to_location (profile, default)

    def gen_get_profile (self, searchterm, replace, profile_location = True, ignore_default = False):
        """Look up the profile for a given searchterm.

        @username: the user whose profile location should be
        returned.
        @profile_location: whether the profile location should
        be returned
        @ignore_default: don't use the default profile if
        no profile is explicitly set.

        Return value: the location of the profile, which
        should be in a suitable form for constructing a
        ProfileStorage object, or the profile name if
        @profile_location is False.
        """
        user = None
        profile = self.__ldap_query ("profilemap", replace)
        if not profile:
            try:
                query = self.xmlquery % searchterm
                user = self.doc.xpathEval(query)[0]
                profile = user.prop("profile")
            except:
                profile = None
        if not profile and not ignore_default:
            try:
                query = "/profiles/default[1][@profile]"
                user = self.doc.xpathEval(query)[0]
                profile = user.prop("profile")
            except:
                profile = None
        
        if not profile_location:
            return profile

        # TODO Check the resulting file path exists
        return self.__profile_name_to_location (profile, user)

    def __save_as(self, filename = None):
        """Save the current version to the given filename"""
        if filename == None:
            filename = self.file

        dprint("Saving UserDatabase to %s\n", filename)
        try:
            os.rename(filename, filename + ".bak")
            backup = 1
        except:
            backup = 0
            pass

        try:
            f = open(filename, 'w')
        except:
            if backup == 1:
                try:
                    os.rename(filename + ".bak", filename)
                    dprint("Restore from %s.bak\n", filename)
                except:
                    dprint("Failed to restore from %s.bak\n", filename)

                raise SystemDatabaseException(
                    _("Could not open %s for writing") % filename)
        try:
            f.write(self.doc.serialize("UTF-8", format=1))
            f.close()
        except:
            if backup == 1:
                try:
                    os.rename(filename + ".bak", filename)
                    dprint("Restore from %s.bak\n", filename)
                except:
                    dprint("Failed to restore from %s.bak\n", filename)

            raise SystemDatabaseException(
                _("Failed to save UserDatabase to %s") % filename)

        self.modified = 0

    def set_default_profile (self, profile):
        """Set the default profile to be used in this database.

        @profile: the location of the profile.
        """
        if profile is None:
            profile = ""
        self.modified = 0
        try:
            default = self.doc.xpathEval("/profiles/default")[0]
            oldprofile = default.prop("profile")
            if oldprofile != profile:
                default.setProp("profile", profile)
                self.modified = 1
        except:
            try:
                profiles = self.doc.xpathEval("/profiles")[0]
            except:
                raise SystemDatabaseException(
                    _("File %s is not a profile configuration") %
                                           (self.file))
            try:
                default = profiles.newChild(None, "default", None)
                default.setProp("profile", profile)
            except:
                raise SystemDatabaseException(
                    _("Failed to add default profile %s to configuration") %
                                           (profile))
            self.modified = 1
        if self.modified == 1:
            self.__save_as()

    def gen_set_profile (self, searchterm, child, profile):
        """Set the profile for a given searchterm.

        @searchterm: the term whose profile location should be set.
        @profile: the location of the profile.
        """
        if profile is None:
            profile = ""
        self.modified = 0
        try:
            query = self.xmlquery % searchterm
            user = self.doc.xpathEval(query)[0]
            oldprofile = user.prop("profile")
            if oldprofile != profile:
                user.setProp("profile", profile)
                self.modified = 1
        except:
            try:
                profiles = self.doc.xpathEval("/profiles")[0]
            except:
                raise SystemDatabaseException(
                    _("File %s is not a profile configuration") % (self.file))
            try:
                user = profiles.newChild(None, child, None)
                user.setProp("name", searchterm)
                user.setProp("profile", profile)
            except:
                raise SystemDatabaseException(
                    _("Failed to add user %s to profile configuration") %
                                           (username))
            self.modified = 1
        if self.modified == 1:
            self.__save_as()

    def gen_is_sabayon_controlled (self, searchterm, replace):
        """Return True if user's configuration was ever under Sabayon's
        control.
        """
        profile = self.__ldap_query ("profilemap", replace)

        if profile:
            return True
        
        try:
            query = self.xmlquery % searchterm
            user = self.doc.xpathEval(query)[0]
        except:
            return False

        if user:
            return True

        return False

    def get_profiles (self):
        """Return the list of currently available profiles.
        This is basically just list of zip files in
        /etc/desktop-profiles, each without the .zip extension.
        """
        list = []
        try:
            for file in os.listdir(config.PROFILESDIR):
                if file[-4:] != ".zip":
                    continue
                list.append(file[0:-4])
        except:
            dprint("Failed to read directory(%s)\n" % (config.PROFILESDIR))
        # TODO: also list remote profiles as found in self.doc
        return list

class UserDatabase(SystemDatabase):
    """Encapsulate a user mapping
    """
    def __init__ (self, db_file = None):
        if db_file is None:
            SystemDatabase.__init__(self, "users.xml")
        else:
            SystemDatabase.__init__(self, db_file)

        self.xmlquery = "/profiles/user[@name='%s']"

    def get_profile (self, username, profile_location = True, ignore_default = False):
        return self.gen_get_profile(username, {"u":username,
            "h":socket.getfqdn()}, profile_location, ignore_default)

    def is_sabayon_controlled (self, username):
        return self.gen_is_sabayon_controlled(username, {"u":username, "h":socket.getfqdn()})

    def set_profile (self, username, profile):
        return self.gen_set_profile (username, "user", profile)

    def get_users (self):
        """Return the list of users on the system. These should
        be real users - i.e. should not include system users
        like nobody, gdm, nfsnobody etc.
        """
        list = []
        try:
            users = pwd.getpwall()
        except:
            raise SystemDatabaseException(_("Failed to get the user list"))

        for user in pwd.getpwall():
            try:
                # remove non-users
                if user[2] < 500:
                    continue
                if user[0] == "nobody":
                    continue
                if user[0] in list:
                    continue
                if user[6] == "" or string.find(user[6], "nologin") != -1:
                    continue
                if user[0][len (user[0]) - 1] == "$":  # Active Directory hosts end in "$"; we don't want to show those as users
                    continue
                list.append(user[0])
            except:
                pass
        return list

class GroupDatabase(SystemDatabase):
    """Encapsulate a user mapping
    """
    def __init__ (self, db_file = None):
        if db_file is None:
            SystemDatabase.__init__(self, "groups.xml")
        else:
            SystemDatabase.__init__(self, db_file)

        self.xmlquery = "/profiles/group[@name='%s']"

    def get_profile (self, groupname, profile_location = True, ignore_default = False):
        return self.gen_get_profile(groupname, {"g":groupname,
            "h":socket.getfqdn()}, profile_location, ignore_default)

    def is_sabayon_controlled (self, groupname):
        return self.gen_is_sabayon_controlled(groupname, {"g":groupname, "h":socket.getfqdn()})

    def set_profile (self, groupname, profile):
        return self.gen_set_profile (groupname, "group", profile)

    def get_groups (self):
        """Return the list of groups on the system. These should
        be real groups - i.e. should not include system groups
        like lp, udev, etc.
        """
        list = []
        try:
            groups = grp.getgrall()
        except:
            raise GroupDatabaseException(_("Failed to get the group list"))

        for group in groups:
            # remove non-groups
            if group[2] < 500:
                continue
            if group[0] == "nogroup":
                continue
            if group[0] in list:
                continue
            # We don't want to include "user" primary groups
            try:
                user = pwd.getpwnam(group[0])
            except:
                user = None
            if user is not None and user[2] == group[2]:
                continue
            list.append(group[0])
        return list

user_database = None
group_database = None

def get_user_database ():
    """Return a UserDatabase singleton"""
    global user_database
    if user_database is None:
        user_database = UserDatabase ()
    return user_database

def get_group_database ():
    """Return a UserDatabase singleton"""
    global group_database
    if group_database is None:
        group_database = GroupDatabase ()
    return group_database
#
# Unit tests
#

def run_unit_tests ():
    testuserfile = "/tmp/test_users.xml"
    testgroupfile = "/tmp/test_groups.xml"
    try:
        os.unlink(testuserfile)
        os.unlink(testgroupfile)
    except:
        pass
    db = UserDatabase(testuserfile)
    db.set_default_profile("default")
    res = db.get_profile("localuser", False)
    assert not res is None
    assert res == "default"
    db.set_profile("localuser", "groupA")
    res = db.get_profile("localuser")
    assert not res is None
    assert res[-28:] == "/desktop-profiles/groupA.zip"
    db.set_profile("localuser", "groupB")
    res = db.get_profile("localuser")
    assert not res is None
    assert res[-28:] == "/desktop-profiles/groupB.zip"
    res = db.get_users()
    print res
    db = GroupDatabase(testgroupfile)
    db.set_default_profile("default")
    res = db.get_profile("localuser", False)
    assert not res is None
    assert res == "default"
    db.set_profile("localgroup", "groupA")
    res = db.get_profile("localgroup")
    assert not res is None
    assert res[-28:] == "/desktop-profiles/groupA.zip"
    db.set_profile("localgroup", "groupB")
    res = db.get_profile("localgroup")
    assert not res is None
    assert res[-28:] == "/desktop-profiles/groupB.zip"
    res = db.get_groups()
    print res

if __name__ == "__main__":
    util.init_gettext ()
    run_unit_tests()
