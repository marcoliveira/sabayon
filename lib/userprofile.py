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

class ModuleLoader:
    """Loads all python modules from a directory allows objects
    to be constructed from said modules using specific constructors
    for each object type."""
    
    def __init__ (self, module_path):
        """Construct a ModuleLoader and will load all available
        python modules from @module_path.
        """
        self.module_path = module_path
        self.modules = []
        self.__load_modules ()

    def __load_module (self, module):
        """Load a python module named @module."""
        cmd = "import " + module
        try:
            exec (cmd)
        except:
            print "Failed to import module '%s': %s" % (module, sys.exc_type)
            return
        self.modules.append (module)
        
    def __load_modules (self):
        """Load all available modules from self.module_path."""
        sys.path.append (self.module_path)
        for file in os.listdir (self.module_path):
            if file[0] == '.':
                continue
            if file[-3:] != ".py":
                continue
            self.__load_module (file[:-3])

    def __construct_object (self, module, constructor, arg):
        """Construct an object by invoking a function named @constructor,
        with @arg as an argument, in the module called @module.
        """
        cmd = ("import %s\nif %s.__dict__.has_key ('%s'):"
               "ret = %s.%s (arg)") % (module, module, constructor, module, constructor)
        try:
            exec (cmd)
        except:
            print "Failed to invoke function '%s.%s': %s" % (module, constructor, sys.exc_type)
            return None

        try:
            ret = ret
        except NameError:
            return None
        return ret
    
    def construct_objects (self, constructor, arg):
        """Construct and return a list of objects by invoking a function
        named @constructor, with @arg as an argument, in each of the
        python modules in self.module_path which contain a function
        by that name.
        """
        objects = []
        for module in self.modules:
            o = self.__construct_object (module, constructor, arg)
            if o != None:
                objects.append (o)
        return objects

module_loader = None
def get_module_loader ():
    """Return a singleton ModuleLoader object."""
    global module_loader
    if module_loader == None:
        module_loader = ModuleLoader (MODULEPATH)
    return module_loader
            
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

class SourceDelegate:
    """An abstract base class for helper classes which can be used
    to intercept and modify changes from a given configuration
    source."""
    
    def __init__ (self, source, namespace_section, change_class):
        """Construct a SourceDelegate object.

        @source: the ProfileSource whose changes the delegate wishes
        to inspect.
        @namepsace_section: the section of @source's configuration
        namespace that the delegate wishes to inspect.
        """
        self.source = source
        self.namespace_section = namespace_section
        self.change_class = change_class

    def handle_change (self, change):
        """Inspect a ProfileChange. Return #True if the change should
        not be passed on any further (i.e. #True == 'handled') and
        return #False if the change should be passed on unmodified.
        """
        raise Exception ("Not implemented")

class ProfileSource (gobject.GObject):
    """An abstract base class which each configuration source must
    implement."""

    __gsignals__ = {
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (ProfileChange, ))
        }

    def __init__ (self, source_name, delegate_constructor = None):
        """Construct a ProfileSource object."""
        gobject.GObject.__init__ (self)
        self.name = source_name
        
        module_loader = get_module_loader ()

        self.delegates = []
        if delegate_constructor:
            self.delegates = module_loader.construct_objects (delegate_constructor, self)
    
    def get_name (self):
        """Returns the configuration source's name."""
        return self.name

    def emit_change (self, change):
        """Pass @change to all register delegates for this source and
        emit a 'changed' signal with @change if none of the delegates
        return #True.
        """
        for delegate in self.delegates:
            if not change.get_name ().startswith (delegate.namespace_section):
                continue
            if delegate.handle_change (change):
                return
        self.emit ("changed", change)
        
    def commit_change (self, change, mandatory = False):
        """Commit a change to profile.

        mandatory: whether the change should be committed such
        that it overrides the user's value.
        """
        #
        # FIXME:
        #   Need to handle changes that originated from
        #   a delegate here e.g.
        # for delegate in self.delegates:
        #     if isinstance (change, delegate.change_class):
        #         delegate.commit_change (change, mandatory)
        #         return
        # self.really_commit_change (change, mandatory)
        #
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

    def __init__ (self, profile_path, profile_file):
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

        #
	# Open the user settings packages and try to install them
	#
	self.profile_storage = storage.ProfileStorage (profile_file)
	try:
	    profile_storage.install (profile_path)
	except:
	    # FIXME: the file doesn't exist or there is a problem this
	    #        should be reported at the UI level
	    pass
        
        module_loader = get_module_loader ()
        
        self.sources = []
        self.sources = module_loader.construct_objects ("get_source",
                                                        self.profile_storage)
        for source in self.sources:
            source.connect ("changed", self.__handle_source_changed)

    def __handle_source_changed (self, source, change):
        self.emit ("changed", change)

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
        def get_name (self):
            return self.key
        def get_type (self):
            return ""
        def get_value (self):
            return self.value

    class LocalTestDelegate (SourceDelegate):
        def __init__ (self, source):
            SourceDelegate.__init__ (self, source, "/bar")
        def handle_change (self, change):
            if change.get_name () == "/bar/foo1":
                return True
            return False

    class LocalTestSource (ProfileSource):
        def __init__ (self):
            ProfileSource.__init__ (self, "local")

    profile = UserProfile ("/tmp/foo", "/tmp/foo-storage")
    assert profile.profile_path == "/tmp/foo"
    assert len (profile.sources) > 0

    testsource = None
    for source in profile.sources:
        if source.get_name () == "test":
            testsource = source
            break;
    assert testsource != None
    assert len (testsource.delegates) == 1

    localsource = LocalTestSource ()
    profile.sources.append (localsource)
    def handle_source_changed (source, change, profile):
        profile.emit ("changed", change)
    localsource.connect ("changed", handle_source_changed, profile)
    assert len (profile.sources) > 1

    localdelegate = LocalTestDelegate (localsource)
    localsource.delegates.append (localdelegate)

    global n_signals
    n_signals = 0
    def handle_changed (profile, change):
        global n_signals
        n_signals += 1
    profile.connect ("changed", handle_changed)

    # Only foo2 and foo3 should get through
    localsource.emit_change (LocalTestChange (localsource, "/bar/foo1", "1"))
    localsource.emit_change (LocalTestChange (localsource, "/bar/foo2", "2"))
    localsource.emit_change (LocalTestChange (localsource, "/bar/foo3", "3"))

    # Only bar2 and bar3 should get through
    testsource.emit_change (testsource.get_test_change ("/foo/bar1", "1"))
    testsource.emit_change (testsource.get_test_change ("/foo/bar2", "2"))
    testsource.emit_change (testsource.get_test_change ("/foo/bar3", "3"))

    assert n_signals == 4
