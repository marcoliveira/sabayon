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

import gconf
import userprofile
import gconfsource
from config import *

class PanelChange (userprofile.ProfileChange):
    def __init__ (self, source, delegate, id):
        userprofile.ProfileChange.__init__ (self, source, delegate)
        self.id = id
    def get_name (self):
        return self.id

class PanelAddedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_type (self):
        return "Panel added"
    def get_value (self):
        return ""
    
class PanelRemovedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_type (self):
        return "Panel removed"
    def get_value (self):
        return ""

class PanelAppletAddedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_type (self):
        return "Panel applet added"
    def get_value (self):
        return ""

class PanelAppletRemovedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_type (self):
        return "Panel applet removed"
    def get_value (self):
        return ""

class PanelObjectAddedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_type (self):
        return "Panel object added"
    def get_value (self):
        return ""

class PanelObjectRemovedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_type (self):
        return "Panel object removed"
    def get_value (self):
        return ""

class PanelDelegate (userprofile.SourceDelegate):
    class PanelThing:
        def __init__ (self, id, added, removed):
            self.id      = id
            self.added   = added
            self.removed = removed
    
    class PanelToplevel (PanelThing):
        def __init__ (self, id, added = False, removed = False):
            PanelDelegate.PanelThing.__init__ (self, id, added, removed)
            
            # FIXME: which attributes do we really need?
            # self.name        = self.client.get_string (PANEL_KEY_BASE + "/toplevels/" + toplevel_id + "/name")
            # self.orientation = self.client.get_string (PANEL_KEY_BASE + "/toplevels/" + toplevel_id + "/orientation")
            # self.expand      = self.client.get_bool   (PANEL_KEY_BASE + "/toplevels/" + toplevel_id + "/expand")
        
    class PanelApplet (PanelThing):
        def __init__ (self, id, added = False, removed = False):
            PanelDelegate.PanelThing.__init__ (self, id, added, removed)
            
            # FIXME: which attributes do we really need?
            # self.toplevel_id = self.client.get_string (PANEL_KEY_BASE + "/applets/" + applet_id + "/toplevel_id")
            # self.bonobo_iid  = self.client.get_string (PANEL_KEY_BASE + "/applets/" + applet_id + "/bonobo_iid")

    class PanelObject (PanelThing):
        def __init__ (self, id, added = False, removed = False):
            PanelDelegate.PanelThing.__init__ (self, id, added, removed)
            
            # FIXME: which attributes do we really need?
            # self.toplevel_id = self.client.get_string (PANEL_KEY_BASE + "/objects/" + object_id + "/toplevel_id")
            # self.object_type = self.client.get_string (PANEL_KEY_BASE + "/objects/" + object_id + "/object_type")

    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, source, PANEL_KEY_BASE)
        self.client = gconf.client_get_default ()

        self.toplevels = {}
        self.applets = {}
        self.objects = {}
        self.__read_panel_config ()

    def __read_panel_config (self):
        for id in self.client.get_list (PANEL_KEY_BASE + "/general/toplevel_id_list", gconf.VALUE_STRING):
            if not self.toplevels.has_key (id):
                self.toplevels[id] = PanelDelegate.PanelToplevel (id, False)
        for id in self.client.get_list (PANEL_KEY_BASE + "/general/applet_id_list", gconf.VALUE_STRING):
            if not self.applets.has_key (id):
                self.applets[id] = PanelDelegate.PanelApplet (id, False)
        for id in self.client.get_list (PANEL_KEY_BASE + "/general/object_id_list", gconf.VALUE_STRING):
            if not self.objects.has_key (id):
                self.objects[id] = PanelDelegate.PanelObject (id, False)

    def __handle_id_list_change (self, change, dict, thing_class, added_class, removed_class):
        if not change.entry.value or \
               change.entry.value.type != gconf.VALUE_LIST or \
               change.entry.value.get_list_type () != gconf.VALUE_STRING:
                return True

        id_list = []
        for v in change.entry.value.get_list ():
            id_list.append (v.get_string ())
            
        added = []
        for id in id_list:
            if dict.has_key (id) and not dict[id].removed:
                continue
            if not dict.has_key (id):
                dict[id] = thing_class (id, True)
            else:
                dict[id].added   = True
                dict[id].removed = False
            added.append (id)

        removed = []
        for id in dict:
            if id in id_list:
                continue
            if dict.has_key (id) and not dict[id].removed:
                dict[id].removed = True
                removed.append (id)

        for id in added:
            self.source.emit ("changed", added_class (self.source, self, id))
        for id in removed:
            self.source.emit ("changed", removed_class (self.source, self, id))

        return True

    def handle_change (self, change):
        if change.entry.key.startswith (PANEL_KEY_BASE + "/toplevels/"):
            toplevel_id = change.entry.key.split ("/")[4]
            if not self.toplevels.has_key (toplevel_id) or \
               self.toplevels[toplevel_id].added or \
               self.toplevels[toplevel_id].removed:
                return True
        
        elif change.entry.key.startswith (PANEL_KEY_BASE + "/objects/"):
            object_id = change.entry.key.split ("/")[4]
            if not self.objects.has_key (object_id) or \
               self.toplevels[object_id].added or \
               self.toplevels[object_id].removed:
                return True
        
        elif change.entry.key.startswith (PANEL_KEY_BASE + "/applets"):
            applet_id = change.entry.key.split ("/")[4]
            if not self.applets.has_key (applet_id) or \
               self.toplevels[applet_id].added or \
               self.toplevels[applet_id].removed:
                return True
        
        elif change.entry.key == PANEL_KEY_BASE + "/general/toplevel_id_list":
            return self.__handle_id_list_change (change,
                                                 self.toplevels,
                                                 PanelDelegate.PanelToplevel,
                                                 PanelAddedChange,
                                                 PanelRemovedChange)
            
        elif change.entry.key == PANEL_KEY_BASE + "/general/applet_id_list":
            return self.__handle_id_list_change (change,
                                                 self.applets,
                                                 PanelDelegate.PanelApplet,
                                                 PanelAppletAddedChange,
                                                 PanelAppletRemovedChange)
            
        elif change.entry.key == PANEL_KEY_BASE + "/general/object_id_list":
            return self.__handle_id_list_change (change,
                                                 self.objects,
                                                 PanelDelegate.PanelObject,
                                                 PanelObjectAddedChange,
                                                 PanelObjectRemovedChange)

        return False

    def __copy_dir (self, src_client, dst_client, dst_address, dir):
        for entry in src_client.all_entries (dir):
            if entry.get_schema_name ():
                gconfsource.associate_schema (dst_address, entry.key, entry_get_schema_name ())
            if entry.value and not entry.get_is_default ():
                dst_client.set (entry.key, entry.value)
        for subdir in src_client.all_dirs (dir):
            self.__copy_dir (src_client, dst_client, dst_address, subdir)

    def __get_current_list (self, dict):
        id_list = []
        for id in dict:
            if dict[id].added:
                continue
            id_list.append (id)
        return id_list

    def __commit_added_change (self, change, mandatory, dict, id_list_name, dir_name):
        if not dict.has_key (change.id):
            return
        
        thing = dict[change.id]
        if not thing.added:
            return

        (client, address) = self.source.get_committing_client_and_address (mandatory)

        self.__copy_dir (self.client, client, address, PANEL_KEY_BASE + "/" + dir_name + "/" + thing.id)
        
        id_list = self.__get_current_list (dict)
        id_list.append (thing.id)
        client.set_list (PANEL_KEY_BASE + "/general/" + id_list_name, gconf.VALUE_STRING, id_list)
        
        thing.added = False
        
    def __commit_removed_change (self, change, mandatory, dict, id_list_name, dir_name):
        if not dict.has_key (change.id):
            return

        thing = dict[change.id]
        if not thing.removed:
            return

        (client, address) = self.source.get_committing_client_and_address (mandatory)

        id_list = self.__get_current_list (dict)
        if thing.id in id_list:
            id_list.remove (thing.id)
            client.set_list (PANEL_KEY_BASE + "/general/" + id_list_name, gconf.VALUE_STRING, id_list)
            gconfsource.recursive_unset (client, PANEL_KEY_BASE + "/" + dir_name + "/" + thing.id)
        
        del dict[change.id]

    def commit_change (self, change, mandatory = False):
        if isinstance (change, PanelAddedChange):
            self.__commit_added_change (change,
                                        mandatory,
                                        self.toplevels,
                                        "toplevel_id_list",
                                        "toplevels")
        elif isinstance (change, PanelRemovedChange):
            self.__commit_removed_change (change,
                                          mandatory,
                                          self.toplevels,
                                          "toplevel_id_list",
                                          "toplevels")
        elif isinstance (change, PanelAppletAddedChange):
            self.__commit_added_change (change,
                                        mandatory,
                                        self.applets,
                                        "applet_id_list",
                                        "applets")
        elif isinstance (change, PanelAppletRemovedChange):
            self.__commit_removed_change (change,
                                          mandatory,
                                          self.applets,
                                          "applet_id_list",
                                          "applets")
        elif isinstance (change, PanelObjectAddedChange):
            self.__commit_added_change (change,
                                        mandatory,
                                        self.objects,
                                        "object_id_list",
                                        "objects")
        elif isinstance (change, PanelObjectRemovedChange):
            self.__commit_removed_change (change,
                                          mandatory,
                                          self.objects,
                                          "object_id_list",
                                          "objects")

def get_gconf_delegate (source):
    return PanelDelegate (source)

#
# Unit tests
#
def run_unit_tests ():
    import gobject
    import os
    import os.path
    import time
    import tempfile
    import shutil

    # Clear out any cruft
    os.system ("gconftool-2 --recursive-unset %s/toplevels/foo" % PANEL_KEY_BASE)
    os.system ("gconftool-2 --recursive-unset %s/objects/foo" % PANEL_KEY_BASE)
    os.system ("gconftool-2 --recursive-unset %s/applets/foo" % PANEL_KEY_BASE)
    time.sleep (1)

    client = gconf.client_get_default ()
    
    for id_list_name in ("toplevel_id_list", "object_id_list", "applet_id_list"):
        id_list = client.get_list (PANEL_KEY_BASE + "/general/" + id_list_name, gconf.VALUE_STRING)
        while "foo" in id_list:
            id_list.remove ("foo")
        client.set_list (PANEL_KEY_BASE + "/general/" + id_list_name, gconf.VALUE_STRING, id_list)

    temp_path = tempfile.mkdtemp (prefix = "test-paneldelegate-")

    # Create a dummy source with a PanelDelegate
    class TempSource (userprofile.ProfileSource):
        def __init__ (self, temp_path):
            userprofile.ProfileSource.__init__ (self, "panel-temp")
            self.delegates.append (PanelDelegate (self))
            self.temp_path = temp_path
            self.defaults_client = None
            self.defaults_address = None
            self.mandatory_client = None
            self.mandatory_address = None
        def get_committing_client_and_address (self, mandatory):
            if not mandatory:
                if not self.defaults_client:
                    (client, address) = gconfsource.get_client_and_address_for_path (self.temp_path + "/.gconf.xml.defaults")
                    self.defaults_client = client
                    self.defaults_address = address
                return (self.defaults_client, self.defaults_address)
            else:
                if not self.mandatory_client:
                    (client, address) = gconfsource.get_client_and_address_for_path (self.temp_path + "/.gconf.xml.mandatory")
                    self.mandatory_client = client
                    self.mandatory_address = address
                return (self.mandatory_client, self.mandatory_address)
    gobject.type_register (TempSource)
    source = TempSource (temp_path)

    # Set up the client
    def handle_notify (client, cnx_id, entry, source):
        source.emit_change (gconfsource.GConfChange (source, entry))
    client.add_dir (PANEL_KEY_BASE + "", gconf.CLIENT_PRELOAD_RECURSIVE)
    notify_id = client.notify_add (PANEL_KEY_BASE + "", handle_notify, source)

    # Trap filtered changes
    global changes
    changes = []
    def handle_change (source, change):
        global changes
        changes.append (change)
    source.connect ("changed", handle_change)

    # Need to run the mainloop to get notifications.
    # The notification is only dispatched once the set
    # operation has complete
    main_loop = gobject.MainLoop ()
    def poll (main_loop):
        while main_loop.get_context ().pending ():
            main_loop.get_context ().iteration (False)

    # Recursively copy a dir
    def copy_dir (client, dst, src):
        for entry in client.all_entries (src):
            key = dst + "/" + os.path.basename (entry.key)
            client.set (key, entry.value)
        for dir in client.all_dirs (src):
            subdir = os.path.basename (dir)
            copy_dir (client, dst + "/" + subdir, src + "/" + subdir)

    # Set random uninterpreted key
    show_program_list = client.get_bool (PANEL_KEY_BASE + "/general/show_program_list")
    client.set_bool (PANEL_KEY_BASE + "/general/show_program_list", not show_program_list)
    poll (main_loop)

    # Set up a panel on the right
    copy_dir (client, PANEL_KEY_BASE + "/toplevels/foo", PANEL_KEY_BASE + "/toplevels/top_panel")
    poll (main_loop)

    # Set up a clock applet
    copy_dir (client, PANEL_KEY_BASE + "/applets/foo", PANEL_KEY_BASE + "/applets/clock")
    client.set_string (PANEL_KEY_BASE + "/applets/foo/toplevel_id", "foo")
    poll (main_loop)
    
    # Set up a menu bar
    copy_dir (client, PANEL_KEY_BASE + "/objects/foo", PANEL_KEY_BASE + "/objects/menu_bar")
    client.set_string (PANEL_KEY_BASE + "/objects/foo/toplevel_id", "foo")
    poll (main_loop)

    # Add the new panel to the list of panels
    toplevels = client.get_list (PANEL_KEY_BASE + "/general/toplevel_id_list", gconf.VALUE_STRING)
    toplevels.append ("foo")
    client.set_list (PANEL_KEY_BASE + "/general/toplevel_id_list", gconf.VALUE_STRING, toplevels)
    poll (main_loop)
    
    # Add the new clock to the list of applets
    applets = client.get_list (PANEL_KEY_BASE + "/general/applet_id_list", gconf.VALUE_STRING)
    applets.append ("foo")
    client.set_list (PANEL_KEY_BASE + "/general/applet_id_list", gconf.VALUE_STRING, applets)
    poll (main_loop)

    # Add the new menu bar to the list of objects
    objects = client.get_list (PANEL_KEY_BASE + "/general/object_id_list", gconf.VALUE_STRING)
    objects.append ("foo")
    client.set_list (PANEL_KEY_BASE + "/general/object_id_list", gconf.VALUE_STRING, objects)
    poll (main_loop)

    time.sleep (3)

    client.set_int (PANEL_KEY_BASE + "/toplevels/foo/hide_delay", 5)
    poll (main_loop)

    assert len (changes) == 4
    for change in changes:
        assert isinstance (change, userprofile.ProfileChange)
    assert isinstance (changes[0], gconfsource.GConfChange)
    assert changes[0].entry.key == PANEL_KEY_BASE + "/general/show_program_list"
    for change in changes[1:4]:
        assert isinstance (change, PanelChange)
        assert change.id == "foo"

    (
        PANEL_ADDED,
        PANEL_APPLET_ADDED,
        PANEL_OBJECT_ADDED
    ) = range (1, 4)
    
    assert isinstance (changes[PANEL_ADDED], PanelAddedChange)
    assert isinstance (changes[PANEL_APPLET_ADDED], PanelAppletAddedChange)
    assert isinstance (changes[PANEL_OBJECT_ADDED], PanelObjectAddedChange)

    source.commit_change (changes[PANEL_ADDED], False)
    
    os.system ("gconftool-2 --shutdown")
    time.sleep (1)

    assert os.access (temp_path + "/.gconf.xml.defaults/apps/panel/general/%gconf.xml", os.F_OK)
    assert os.access (temp_path + "/.gconf.xml.defaults/apps/panel/toplevels/foo/%gconf.xml", os.F_OK)

    changes = []

    # Remove the menu bar again
    while "foo" in objects:
        objects.remove ("foo")
    client.set_list (PANEL_KEY_BASE + "/general/object_id_list", gconf.VALUE_STRING, objects)
    poll (main_loop)
    
    # Remove the clock again
    while "foo" in applets:
        applets.remove ("foo")
    client.set_list (PANEL_KEY_BASE + "/general/applet_id_list", gconf.VALUE_STRING, applets)
    poll (main_loop)
    
    # Remove the panel again
    while "foo" in toplevels:
        toplevels.remove ("foo")
    client.set_list (PANEL_KEY_BASE + "/general/toplevel_id_list", gconf.VALUE_STRING, toplevels)
    poll (main_loop)

    # Set random uninterpreted key back again
    client.set_bool (PANEL_KEY_BASE + "/general/show_program_list", show_program_list)
    poll (main_loop)
    
    # Shutdown the client again
    client.notify_remove (notify_id)
    client.remove_dir (PANEL_KEY_BASE + "")

    assert len (changes) == 4
    for change in changes:
        assert isinstance (change, userprofile.ProfileChange)
    for change in changes[:3]:
        assert isinstance (change, PanelChange)
        assert change.id == "foo"
    assert isinstance (changes[3], gconfsource.GConfChange)
    assert changes[3].entry.key == PANEL_KEY_BASE + "/general/show_program_list"

    (
        PANEL_OBJECT_REMOVED,
        PANEL_APPLET_REMOVED,
        PANEL_REMOVED
    ) = range (3)
    
    assert isinstance (changes[PANEL_OBJECT_REMOVED], PanelObjectRemovedChange)
    assert isinstance (changes[PANEL_APPLET_REMOVED], PanelAppletRemovedChange)
    assert isinstance (changes[PANEL_REMOVED], PanelRemovedChange)

    source.commit_change (changes[PANEL_REMOVED], False)

    print temp_path
    os.system ("gconftool-2 --shutdown")
    time.sleep (1)
    
    assert not os.access (temp_path + "/.gconf.xml.defaults/apps/panel/toplevels/foo/%gconf.xml", os.F_OK)

    # Bye, bye cruft
    os.system ("gconftool-2 --recursive-unset %s/toplevels/foo" % PANEL_KEY_BASE)
    os.system ("gconftool-2 --recursive-unset %s/objects/foo" % PANEL_KEY_BASE)
    os.system ("gconftool-2 --recursive-unset %s/applets/foo" % PANEL_KEY_BASE)

    #shutil.rmtree (temp_path, True)
