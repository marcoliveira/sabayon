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
import time
import util
import gobject
import gconf
import userprofile
import storage
import errno

class GConfChange (userprofile.ProfileChange):
    """Encapsulates a change to a GConf key."""
    
    def __init__ (self, source, entry):
        """Construct a GConfChange from a GConfEntry."""
        userprofile.ProfileChange.__init__ (self, source)
        self.entry = entry

    def get_name (self):
        """Return the path to the GConf key which changed."""
        return self.entry.key

    def get_type (self):
        """Return the type of the GConf key which changed."""
        if not self.entry.value:
            return "None"
        elif self.entry.value.type == gconf.VALUE_STRING:
            return "String"
        elif self.entry.value.type == gconf.VALUE_INT:
            return "Integer"
        elif self.entry.value.type == gconf.VALUE_FLOAT:
            return "Floating Point"
        elif self.entry.value.type == gconf.VALUE_BOOL:
            return "Bool"
        elif self.entry.value.type == gconf.VALUE_SCHEMA:
            return "Schema"
        elif self.entry.value.type == gconf.VALUE_LIST:
            return "List"
        elif self.entry.value.type == gconf.VALUE_PAIR:
            return "Pair"
        else:
            return "Invalid"
        
    def get_value (self):
        """Return the value of the GConf key which changed."""
        if self.entry.value:
            return self.entry.value.to_string ()
        else:
            return "(unset)"

gobject.type_register (GConfChange)

class GConfSource (userprofile.ProfileSource):
    """GConf user profile source."""
    
    def __init__ (self, profile_storage, source_name):
        """Construct a GConfSource

        profile_storage: storage object
	path to commit changes to - defaults
        are strored in .gconf.xml.defaults and mandatory
        changes are stored in .gconf.xml.mandatory
        """
        userprofile.ProfileSource.__init__ (self, source_name)

        self.profile_storage  = profile_storage
        self.client           = gconf.client_get_default ()
        self.notify_id        = 0
        self.defaults_client  = None
        self.mandatory_client = None

    def __get_client (self, mandatory):
        """Get a GConfClient using either .gconf.xml.defaults or
        .gconf.xml.mandatory (in the temporary profile location)
        as its source.

        mandatory: whether to get the mandatory or defaults source
        """
        def get_client_for_path (path):
            try:
                os.makedirs (path)
            except OSError, err:
                if err.errno != errno.EEXIST:
                    raise err
            engine = gconf.engine_get_for_address ("xml:readwrite:" + path)
            return gconf.client_get_for_engine (engine)

        if not mandatory:
            if not self.defaults_client:
                self.defaults_client = get_client_for_path (
		               self.profile_storage.get_directory() +
			       "/.gconf.xml.defaults")
            return self.defaults_client
        else:
            if not self.mandatory_client:
                self.mandatory_client = get_client_for_path (
		               self.profile_storage.get_directory() +
			       "/.gconf.xml.mandatory")
            return self.mandatory_client

    def commit_change (self, change, mandatory = False):
        """Commit a GConf change to the profile."""
        client = self.__get_client (mandatory)
        if change.entry.value:
            client.set (change.entry.key, change.entry.value)
        else:
            client.unset (change.entry.key)
        
    def start_monitoring (self):
        """Start monitoring for GConf changes. Note that this
        is seriously resource intensive as must load the value
        of all existing keys so that we can determine whether
        a write to the database resulted in an actual change
        in the value of the key.
        """
        if self.notify_id != 0:
            return
        
        def handle_notify (client, cnx_id, entry, self):
            if entry.get_is_default () == True:
                entry.value = None
            self.emit_change (GConfChange (self, entry))
    
        self.client.add_dir ("/", gconf.CLIENT_PRELOAD_RECURSIVE)
        self.notify_id = self.client.notify_add ("/", handle_notify, self)

    def stop_monitoring (self):
        """Stop monitoring for GConf changes."""
        if self.notify_id == 0:
            return

        self.client.notify_remove (self.notify_id)
        self.notify_id = 0
        self.client.remove_dir ("/")

    def sync_changes (self):
        """Ensure that all committed changes are saved to disk."""
        
        # FIXME: it would be nicer if we just wrote directly
        #        to the defaults and mandatory sources
        os.system ("gconftool-2 --shutdown")
        time.sleep (1)

    def apply (self):
        """Apply the profile by writing the default and mandatory
        sources location to ~/.gconf.path.defaults and
        ~/.gconf.path.mandatory.

        Note that $(sysconfdir)/gconf/2/path needs to contain
        something like the following in order for this to work:

        include $(HOME)/.gconf.path.mandatory
        xml:readwrite:$(HOME)/.gconf
        include $(HOME)/.gconf.path.defaults
        """
        
        def write_path_file (filename, source):
            """Write a GConf path file. First try writing to a
            temporary file and move it over the original. Failing
            that, write directly to the original.
            """
            temp = filename + ".new"
            try:
                f = file (temp, "w")
            except:
                temp = None
                f = file (filename, "w")

            try:
                f.write (source + "\n")
                f.close ()
            except:
                if temp != None:
                    os.remove (temp)
                raise

            if temp != None:
                os.rename (temp, filename)

        write_path_file (util.get_home_dir () + "/.gconf.path.defaults",
                         "xml:readonly:" +
			 self.profile_storage.get_directory() +
			 "/.gconf.xml.defaults")
        write_path_file (util.get_home_dir () + "/.gconf.path.mandatory",
                         "xml:readonly:" +
			 self.profile_storage.get_directory() +
			 "/.gconf.xml.mandatory")

gobject.type_register (GConfSource)

def get_source (profile_storage):
    return GConfSource (profile_storage, "GConf")

#
# Unit tests
#
def run_unit_tests ():
    import tempfile
    import shutil
    
    main_loop = gobject.MainLoop ()

    temp_path = tempfile.mkdtemp (prefix = "test-gconfprofile-")

    profile_storage = storage.ProfileStorage("GConfTest.zip")
    try:
	profile_storage.install(temp_path)
    except:
        pass
    source = get_source (profile_storage)

    # Remove any stale path files
    try:
        os.remove (util.get_home_dir () + "/.gconf.path.defaults")
        os.remove (util.get_home_dir () + "/.gconf.path.mandatory")
    except:
        pass

    # Need to shutdown the daemon to ensure its not using stale paths
    os.system ("gconftool-2 --shutdown")
    time.sleep (1)

    # Make sure there's no stale keys from a previous run
    # FIXME: gconf_client_recursive_unset() has no wrapping
    # source.client.recursive_unset ("/tmp/test-gconfprofile")
    os.system ("gconftool-2 --recursive-unset /tmp/test-gconfprofile")
    time.sleep (1)

    global changes
    changes = []
    def handle_changed (source, change):
        global changes
        changes.append (change)
    source.connect ("changed", handle_changed)

    source.start_monitoring ()

    # Need to run the mainloop to get notifications.
    # The notification is only dispatched once the set
    # operation has complete
    # We poll after each set because otherwise GConfClient
    # will dispatch the two notifications for the same key
    def poll (main_loop):
        while main_loop.get_context ().pending ():
            main_loop.get_context ().iteration (False)
        
    source.client.set_bool ("/tmp/test-gconfprofile/t1", True)
    poll (main_loop)
    source.client.set_bool ("/tmp/test-gconfprofile/t1", False)
    poll (main_loop)
    source.client.set_bool ("/tmp/test-gconfprofile/t2", True)
    poll (main_loop)
    source.client.set_int ("/tmp/test-gconfprofile/t3", 3)
    poll (main_loop)
    
    source.stop_monitoring ()
    
    assert len (changes) == 4
    assert changes[3].entry.key == "/tmp/test-gconfprofile/t3"
    source.commit_change (changes[3])
    
    assert changes[2].entry.key == "/tmp/test-gconfprofile/t2"
    source.commit_change (changes[2], True)
    
    assert changes[1].entry.key == "/tmp/test-gconfprofile/t1"
    assert changes[0].entry.key == "/tmp/test-gconfprofile/t1"

    # source.client.recursive_unset ("/tmp/test-gconfprofile")
    os.system ("gconftool-2 --recursive-unset /tmp/test-gconfprofile")
    
    source.sync_changes ()

    assert os.access (temp_path + "/.gconf.xml.defaults/tmp/test-gconfprofile/%gconf.xml", os.F_OK)
    assert os.access (temp_path + "/.gconf.xml.mandatory/tmp/test-gconfprofile/%gconf.xml", os.F_OK)

    source.apply ()

    assert os.access (util.get_home_dir () + "/.gconf.path.defaults", os.F_OK)
    assert os.access (util.get_home_dir () + "/.gconf.path.mandatory", os.F_OK)

    # We need to clear the cache because GConfClient doesn't know
    # some new sources have been added to the sources stack so it
    # won't see the value we put in the mandatory source
    source.client.clear_cache ()
    
    entry = source.client.get_entry ("/tmp/test-gconfprofile/t3", "", False)
    assert entry.value
    assert entry.value.type == gconf.VALUE_INT
    assert entry.value.get_int () == 3
    assert not entry.get_is_default ()
    assert entry.get_is_writable ()
    
    entry = source.client.get_entry ("/tmp/test-gconfprofile/t2", "", False)
    assert entry.value
    assert entry.value.type == gconf.VALUE_BOOL
    assert entry.value.get_bool () == True
    assert not entry.get_is_default ()
    assert not entry.get_is_writable ()

    # Shutdown the daemon and remove the path files so we don't screw
    # too much with the running session
    os.system ("gconftool-2 --shutdown")
    time.sleep (1)

    os.remove (util.get_home_dir () + "/.gconf.path.defaults")
    os.remove (util.get_home_dir () + "/.gconf.path.mandatory")
    
    shutil.rmtree (temp_path, True)
