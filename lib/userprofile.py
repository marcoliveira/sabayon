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

import os
import sys
import gobject
from config import *
import storage

class ProfileChange (gobject.GObject):
    """Abstract base class for encapsulating profile changes."""
    
    def __init__ (self, source):
        """Construct a ProfileChange object.

        source: the ProfileSource from which the change came.
        """
        gobject.GObject.__init__ (self)
        self.source = source

    def get_source (self):
        """Get the ProfileSource from which this change came."""
        return self.source

    def get_source_name (self):
        """Return the name of the configuration source."""
        self.source.get_name ()

    def get_name (self):
        """Return the name of the configuration item which changed."""
        raise Exception ("Not implemented")

    def get_type (self):
        """Return the type of the configuration item which changed."""
        raise Exception ("Not implemented")

    def get_value (self):
        """Return the value of the configuration item which changed."""
        raise Exception ("Not implemented")

gobject.type_register (ProfileChange)

class ProfileSource (gobject.GObject):
    """An abstract base class which each configuration source must
    implement."""

    __gsignals__ = {
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (ProfileChange, ))
        }

    def __init__ (self, source_name):
        """Construct a ProfileSource object."""
        gobject.GObject.__init__ (self)
        self.name = source_name

    def get_name (self):
        """Returns the configuration source's name."""
        return self.name

    def emit_change (self, change):
        self.emit ("changed", change)
        
    def commit_change (self, change, mandatory = False):
        """Commit a change to profile.

        mandatory: whether the change should be committed such
        that it overrides the user's value.
        """
        raise Exception ("Not Implemented")

    def start_monitoring (self):
        """Start monitoring for configuration changes."""
        raise Exception ("Not implemented")

    def stop_monitoring (self):
        """Stop monitoring for configuration changes."""
        raise Exception ("Not implemented")

    def sync_changes (self):
        """Save all committed changes to disk."""
        raise Exception ("Not implemented")

    def apply (self):
        """Apply profile to the current user's environment."""
        raise Exception ("Not implemented")

gobject.type_register (ProfileSource)

class UserProfile (gobject.GObject):
    """An encapsulation of the user profile and backend sources."""
    
    __gsignals__ = {
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (ProfileChange, ))
        }

    def __init__ (self, profile_path, profile_file, module_path = MODULEPATH):
        """Construct a UserProfile

        profile_path: temporary path to which configuration sources
        should commit changes.
	profile_file: path to the file containing the user settings,
	it may not exist yet
        module_path: optional path from which configuration modules
        should be loaded
        """
        gobject.GObject.__init__ (self)

        self.profile_path = profile_path
        self.profile_file = profile_file
        self.module_path  = module_path

        #
	# Open the user settings packages and try to install them
	#
	self.profile_storage = storage.ProfileStorage(profile_file)
	try:
	    profile_storage.install(profile_path)
	except:
	    # FIXME: the file doesn't exist or there is a problem this
	    #        should be reported at the UI level
	    pass
        
        self.sources = []
        self.__load_sources (self.module_path)

    def __handle_source_changed (self, source, change):
        self.emit ("changed", change)

    def __load_source (self, module_name):
        """Load a configuration module named module_name. The module
        should have a toplevel function 'get_source' returns
        an object which sub-classes ProfileSource.

        module_name: the configuration sources's name.
        """
        cmd = ("import %s\nif %s.__dict__.has_key ('get_source'):"
               "source = %s.get_source (self.profile_storage)") % (module_name, module_name, module_name)
        try:
            exec (cmd)
        except:
            print "Failed to import module '%s': %s" % (module_name, sys.exc_type)
            return

        try:
            source = source
        except NameError:
            return

        source.connect ("changed", self.__handle_source_changed)
        self.sources.append (source)
        
    def __load_sources (self, module_path):
        """Load all available configuration modules from module_path."""
        sys.path.append (module_path)
        for file in os.listdir (module_path):
            if file[0] == '.':
                continue
            if file[-3:] != ".py":
                continue
            self.__load_source (file[:-3])
        
    def start_monitoring (self):
        """Start monitoring for configuration changes."""
        for s in self.sources:
            s.start_monitoring ()

    def stop_monitoring (self):
        """Stop monitoring for configuration changes."""
        for s in self.sources:
            s.stop_monitoring ()

    def sync_changes (self):
        """Save all committed changes to disk."""
        for s in self.sources:
            s.sync_changes ()

    def apply (self):
        """Apply profile to the current user's environment."""
        for s in self.sources:
            s.apply ()

gobject.type_register (UserProfile)

#
# Unit tests
#
def run_unit_tests ():
    class LocalTestChange (ProfileChange):
        def __init__ (self, source, key, value):
            ProfileChange.__init__ (self, source)
            self.key = key
            self.value = value

    class LocalTestSource (ProfileSource):
        def __init__ (self):
            ProfileSource.__init__ (self, "local")

    profile = UserProfile ("/tmp/foo", "./storage-modules")
    assert profile.profile_path == "/tmp/foo"
    assert len (profile.sources) > 0

    testsource = None
    for source in profile.sources:
        if source.get_name () == "test":
            testsource = source
            break;
    assert testsource != None

    localsource = LocalTestSource ()
    profile.sources.append (localsource)
    def handle_source_changed (source, change, profile):
        profile.emit ("changed", change)
    localsource.connect ("changed", handle_source_changed, profile)
    assert len (profile.sources) > 1

    global n_signals
    n_signals = 0
    def handle_changed (profile, change):
        global n_signals
        n_signals += 1
    
    profile.connect ("changed", handle_changed)

    localsource.emit_change (LocalTestChange (localsource, "foo", "1"))
    localsource.emit_change (LocalTestChange (localsource, "foo", "2"))

    testsource.emit_change (testsource.get_test_change ("bar", "1"))
    testsource.emit_change (testsource.get_test_change ("bar", "2"))

    assert n_signals == 4
