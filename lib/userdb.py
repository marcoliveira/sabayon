#!/usr/bin/env python
import sys
import string
import pwd
import os
import libxml2
import config
import util

defaultConf="""<profiles>
  <default profile="default"/>
</profiles>"""

def libxml2_no_error_callback(ctx, str):
    pass

libxml2.registerErrorHandler(libxml2_no_error_callback, "")

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

    def get_profile (self, username):
        """Look up the profile for a given username.

        @username: the user whose profile location should be
        returned.

        Return value: the location of the profile. The location
        should  be in a suitable form for constructing a
        ProfileStorage object.
        """
	try:
	    query = "/profiles/user[@name='%s']" % username
	    user = self.doc.xpathEval(query)[0]
	    profile = user.prop("profile")
	except:
	    profile = None
	if profile is None or profile == "":
	    try:
	        query = "string(/profiles/default[1]/@profile)"
	        profile = self.doc.xpathEval(query)
	    except:
	        profile = None
	if profile == "":
	    profile = None
	if profile is None:
	    return None
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
	    return None

        # TODO Check the resulting file path exists
        return profile

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

    def set_profile (self, username, profile):
        """Set the profile for a given username.

        @username: the user whose profile location should be
        set.
        @profile: the location of the profile.
        """
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
	    for file in os.listdir('/etc/desktop-profiles'):
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
		if user[2] < 1000:
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
    res = db.get_profile("localuser")
    if res is None:
        print "get_profile failed to return a value"
    if res[-29:] != "/desktop-profiles/default.zip":
        print "get_profile returned the wrong value"
    db.set_profile("localuser", "groupA")
    res = db.get_profile("localuser")
    if res is None:
        print "get_profile failed to return a value"
    if res[-28:] != "/desktop-profiles/groupA.zip":
        print "get_profile returned a wrong value, expected groupA.zip got", res
    db.set_profile("localuser", "groupB")
    res = db.get_profile("localuser")
    if res is None:
        print "get_profile failed to return a value"
    if res[-28:] != "/desktop-profiles/groupB.zip":
        print "get_profile returned a wrong value, expected groupB.zip got", res
        

if __name__ == "__main__":
    util.init_gettext ()
    run_unit_tests()
