#!/usr/bin/env python

import os
from config import *

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
            db_file = os.path.join (PROFILESDIR, "users.xml")

        self.users = {
            "markmc"  : "foo",
            "DV"      : "bar",
            "jdennis" : None
        }

    def get_profile (self, username):
        """Look up the profile for a given username.

        @username: the user whose profile location should be
        returned.

        Return value: the location of the profile. The location
        should  be in a suitable form for constructing a
        ProfileStorage object.
        """
        if self.users.has_key (username):
            return self.users[username]
        else:
            return None

    def set_profile (self, username, profile):
        """Set the profile for a given username.

        @username: the user whose profile location should be
        set.
        @profile: the location of the profile.
        """
        if self.users.has_key (username):
            self.users[username] = profile

    def get_profiles (self):
        """Return the list of currently available profiles.
        This is basically just list of zip files in
        /etc/desktop-profiles, each without the .zip extension.
        """
        return ["foo", "bar", "blaa"]

    def get_users (self):
        """Return the list of users on the system. These should
        be real users - i.e. should not include system users
        like nobody, gdm, nfsnobody etc.
        """
        return self.users.keys ()

user_database = None
def get_database ():
    """Return a UserDatabase singleton"""
    global user_database
    if user_database is None:
        user_database = UserDatabase ()
    return user_database
