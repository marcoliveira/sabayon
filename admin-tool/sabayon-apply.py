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

if __name__ == '__main__':
    import sys

    def lookup_users_profile ():
        # FIXME: implement
        sys.stderr.write ("Not implemented\n")
        raise NotImplementedError

    if len (sys.argv) == 1:
        profile_file = lookup_users_profile ()
    elif len (sys.argv) == 2:
        profile_file = sys.argv[1]
    else:
        sys.stderr.write ("Usage: %s [<profile-file>]\n" % sys.argv[0])
        sys.exit (1)

    import util
    import userprofile
    
    def dprint (fmt, *args):
        util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

    dprint ("Applying profile '%s' for user '%s'" %
            (profile_file, util.get_user_name ()))

    profile = userprofile.UserProfile (profile_file)
    profile.apply ()

    dprint ("Finished applying profile '%s' for user '%s'" %
            (profile_file, util.get_user_name ()))
