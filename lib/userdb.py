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

import sys
import string
import pwd
import os
import libxml2
import config
import util
import cache

defaultConf="""<profiles>
  <default profile=""/>
</profiles>"""

# make sure to initialize the cache first
# this will make sure we can handle disconnection
# and initialize libxml2 environment
cache.initialize()

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_USERDB, fmt % args)

class UserDatabaseException (Exception):
    pass

class UserDatabase:
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
        """Create a UserDatabase object.

        @db_file: an (optional) path which specifes the location
        of the database file. If not specified, the default
        location of /etc/desktop-profiles/users.xml is used.
        """
        if db_file is None:
            file = os.path.join (config.PROFILESDIR, "users.xml")
	elif db_file[0] != '/':
            file = os.path.join (config.PROFILESDIR, db_file)
	else:
	    file = db_file
	self.file = file;
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
	                                  libxml2.XML_PARSE_NOBLANKS);

    def __del__ (self):
        if self.doc != None:
	    self.doc.freeDoc()

    def __profile_name_to_location (self, profile, node):
        if not profile:
            return None

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
		   base != os.path.join (config.PROFILESDIR, "users.xml"):
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
	    ret = libxml2.URIUnescapeString(profile, len(profile), None)
        dprint("Converted profile name '%s' to location '%s'\n",
               orig_profile, profile)
        return profile

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

    def get_profile (self, username, profile_location = True, ignore_default = False):
        """Look up the profile for a given username.

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
	try:
	    query = "/profiles/user[@name='%s']" % username
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

	    raise UserDatabaseException(
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

	    raise UserDatabaseException(
	              _("Failed to save UserDatabase to %s") % filename)
	
	self.modified = 0

    def set_default_profile (self, profile):
        """Set the default profile to be used for all users.

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
		raise UserDatabaseException(
			  _("File %s is not a profile configuration") %
                                           (self.file))
	    try:
		default = profiles.newChild(None, "default", None)
		default.setProp("profile", profile)
	    except:
		raise UserDatabaseException(
			  _("Failed to add default profile %s to configuration") %
                                           (profile))
	    self.modified = 1
	if self.modified == 1:
	    self.__save_as()

    def set_profile (self, username, profile):
        """Set the profile for a given username.

        @username: the user whose profile location should be
        set.
        @profile: the location of the profile.
        """
        if profile is None:
            profile = ""
	self.modified = 0
	try:
	    query = "/profiles/user[@name='%s']" % username
	    user = self.doc.xpathEval(query)[0]
	    oldprofile = user.prop("profile")
	    if oldprofile != profile:
	        user.setProp("profile", profile)
		self.modified = 1
	except:
	    try:
		profiles = self.doc.xpathEval("/profiles")[0]
	    except:
		raise UserDatabaseException(
			  _("File %s is not a profile configuration") %
                                           (self.file))
	    try:
		user = profiles.newChild(None, "user", None)
		user.setProp("name", username)
		user.setProp("profile", profile)
	    except:
		raise UserDatabaseException(
			  _("Failed to add user %s to profile configuration") %
                                           (username))
	    self.modified = 1
	if self.modified == 1:
	    self.__save_as()
	
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

    def get_users (self):
        """Return the list of users on the system. These should
        be real users - i.e. should not include system users
        like nobody, gdm, nfsnobody etc.
        """
	list = []
	try:
	    users = pwd.getpwall()
	except:
	    raise UserDatabaseException(_("Failed to get the user list"))

	for user in pwd.getpwall():
	    try:
	        # remove non-users
		if user[2] < 500:
		    continue
		if user[0] in list:
		    continue
		if user[6] == "" or string.find(user[6], "nologin") != -1:
		    continue
		list.append(user[0])
	    except:
		pass
	return list



user_database = None
def get_database ():
    """Return a UserDatabase singleton"""
    global user_database
    if user_database is None:
        user_database = UserDatabase ()
    return user_database

#
# Unit tests
#
def run_unit_tests ():
    testfile = "/tmp/test_users.xml"
    try:
        os.unlink(testfile)
    except:
        pass
    db = UserDatabase(testfile)
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

if __name__ == "__main__":
    util.init_gettext ()
    run_unit_tests()
