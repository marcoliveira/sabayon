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
import userprofile

class TestChange (userprofile.ProfileChange):
    def __init__ (self, source, key, value):
        userprofile.ProfileChange.__init__ (self, source)
        self.key = key
        self.value = value
    def get_id (self):
        return self.key
    def get_short_description (self):
        return self.key

gobject.type_register (TestChange)

class TestDelegate (userprofile.SourceDelegate):
    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, source, "/foo")

    def handle_change (self, change):
        if change.get_id () == "/foo/bar1":
            return True
        return False

def get_test_delegate (source):
    return TestDelegate (source)

class TestSource (userprofile.ProfileSource):
    def __init__ (self, profile_storage):
        userprofile.ProfileSource.__init__ (self, "test", "get_test_delegate")
        self.profile_storage = profile_storage

    def commit_change (self, change):
        pass
    def start_monitoring (self):
        pass
    def stop_monitoring (self):
        pass
    def sync_changes (self):
        pass
    def apply (self):
        pass

    def get_test_change (self, key, value):
        ret = TestChange (self, key, value)
        return ret

gobject.type_register (TestSource)
    
def get_source (profile_storage):
    return TestSource (profile_storage)
