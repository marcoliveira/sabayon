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
import gconf
import userprofile

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
        PanelChange.__init__ (self, source, id)
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
    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, source, "/apps/panel")
        self.client = gconf.client_get_default ()

        self.toplevels = {}
        self.applets = {}
        self.objects = {}
        self.__read_panel_config ()

    def __read_panel_config (self):
        for id in self.client.get_list ("/apps/panel/general/toplevel_id_list", gconf.VALUE_STRING):
            self.__add_toplevel (id)
        for id in self.client.get_list ("/apps/panel/general/applet_id_list", gconf.VALUE_STRING):
            self.__add_applet (id)
        for id in self.client.get_list ("/apps/panel/general/object_id_list", gconf.VALUE_STRING):
            self.__add_object (id)

    def __add_toplevel (self, toplevel_id):
        assert not self.toplevels.has_key (toplevel_id)

        # FIXME: which attributes do we really need?
        name        = self.client.get_string ("/apps/panel/toplevels/" + toplevel_id + "/name")
        orientation = self.client.get_string ("/apps/panel/toplevels/" + toplevel_id + "/orientation")
        expand      = self.client.get_bool   ("/apps/panel/toplevels/" + toplevel_id + "/expand")
        
        self.toplevels[toplevel_id] = ( name, orientation, expand )

    def __add_applet (self, applet_id):
        assert not self.applets.has_key (applet_id)
        
        # FIXME: which attributes do we really need?
        toplevel_id = self.client.get_string ("/apps/panel/applets/" + applet_id + "/toplevel_id")
        bonobo_iid  = self.client.get_string ("/apps/panel/applets/" + applet_id + "/bonobo_iid")
        
        # if not self.toplevels.has_key (toplevel_id):
        #     continue
        
        self.applets[applet_id] = ( toplevel_id, bonobo_iid )

    def __add_object (self, object_id):
        assert not self.objects.has_key (object_id)
        
        # FIXME: which attributes do we really need?
        toplevel_id = self.client.get_string ("/apps/panel/objects/" + object_id + "/toplevel_id")
        object_type = self.client.get_string ("/apps/panel/objects/" + object_id + "/object_type")
        
        # if not self.toplevels.has_key (toplevel_id):
        #     continue
        
        self.objects[object_id] = ( toplevel_id, object_type )
        
    def __handle_id_list_change (self, change, dict, add_func, added_class, removed_class):
        if not change.entry.value or \
               change.entry.value.type != gconf.VALUE_LIST or \
               change.entry.value.get_list_type () != gconf.VALUE_STRING:
                return True

        id_list = []
        for v in change.entry.value.get_list ():
            id_list.append (v.get_string ())
            
        added = []
        for id in id_list:
            if dict.has_key (id):
                continue
            add_func (id)
            added.append (id)

        removed = []
        for id in dict:
            if id in id_list:
                continue
            removed.append (id)

        for id in added:
            self.source.emit ("changed", added_class (self.source, self, id))
        for id in removed:
            self.source.emit ("changed", removed_class (self.source, self, id))
            del dict[id]

        return True

    def handle_change (self, change):
        if change.entry.key.startswith ("/apps/panel/toplevels/"):
            toplevel_id = change.entry.key.split ("/")[4]
            if not self.toplevels.has_key (toplevel_id):
                return True
        
        elif change.entry.key.startswith ("/apps/panel/objects/"):
            object_id = change.entry.key.split ("/")[4]
            if not self.objects.has_key (object_id):
                return True
        
        elif change.entry.key.startswith ("/apps/panel/applets"):
            applet_id = change.entry.key.split ("/")[4]
            if not self.applets.has_key (applet_id):
                return True
        
        elif change.entry.key == "/apps/panel/general/toplevel_id_list":
            return self.__handle_id_list_change (change,
                                                 self.toplevels,
                                                 self.__add_toplevel,
                                                 PanelAddedChange,
                                                 PanelRemovedChange)
            
        elif change.entry.key == "/apps/panel/general/applet_id_list":
            return self.__handle_id_list_change (change,
                                                 self.applets,
                                                 self.__add_applet,
                                                 PanelAppletAddedChange,
                                                 PanelAppletRemovedChange)
            
        elif change.entry.key == "/apps/panel/general/object_id_list":
            return self.__handle_id_list_change (change,
                                                 self.objects,
                                                 self.__add_object,
                                                 PanelObjectAddedChange,
                                                 PanelObjectRemovedChange)

        return False

    def commit_change (self, change, mandatory = False):
        pass

def get_gconf_delegate (source):
    return PanelDelegate (source)

#
# Unit tests
#
def run_unit_tests ():
    import gobject
    import gconfsource
    import os
    import os.path
    import time

    # Clear out any cruft
    os.system ("gconftool-2 --recursive-unset /apps/panel/toplevels/foo")
    os.system ("gconftool-2 --recursive-unset /apps/panel/objects/foo")
    os.system ("gconftool-2 --recursive-unset /apps/panel/applets/foo")
    time.sleep (1)

    # Create a dummy source with a PanelDelegate
    class TempSource (userprofile.ProfileSource):
        def __init__ (self):
            userprofile.ProfileSource.__init__ (self, "panel-temp")
            self.delegates.append (PanelDelegate (self))
    gobject.type_register (TempSource)
    source = TempSource ()

    # Set up the client
    def handle_notify (client, cnx_id, entry, source):
        source.emit_change (gconfsource.GConfChange (source, entry))
    client = gconf.client_get_default ()
    client.add_dir ("/apps/panel", gconf.CLIENT_PRELOAD_RECURSIVE)
    notify_id = client.notify_add ("/apps/panel", handle_notify, source)

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
    show_program_list = client.get_bool ("/apps/panel/general/show_program_list")
    client.set_bool ("/apps/panel/general/show_program_list", not show_program_list)
    poll (main_loop)

    # Set up a panel on the right
    copy_dir (client, "/apps/panel/toplevels/foo", "/apps/panel/toplevels/top_panel")
    poll (main_loop)

    # Set up a clock applet
    copy_dir (client, "/apps/panel/applets/foo", "/apps/panel/applets/clock")
    client.set_string ("/apps/panel/applets/foo/toplevel_id", "foo")
    poll (main_loop)
    
    # Set up a menu bar
    copy_dir (client, "/apps/panel/objects/foo", "/apps/panel/objects/menu_bar")
    client.set_string ("/apps/panel/objects/foo/toplevel_id", "foo")
    poll (main_loop)

    # Add the new panel to the list of panels
    toplevels = client.get_list ("/apps/panel/general/toplevel_id_list", gconf.VALUE_STRING)
    toplevels.append ("foo")
    client.set_list ("/apps/panel/general/toplevel_id_list", gconf.VALUE_STRING, toplevels)
    poll (main_loop)
    
    # Add the new clock to the list of applets
    applets = client.get_list ("/apps/panel/general/applet_id_list", gconf.VALUE_STRING)
    applets.append ("foo")
    client.set_list ("/apps/panel/general/applet_id_list", gconf.VALUE_STRING, applets)
    poll (main_loop)

    # Add the new menu bar to the list of objects
    objects = client.get_list ("/apps/panel/general/object_id_list", gconf.VALUE_STRING)
    objects.append ("foo")
    client.set_list ("/apps/panel/general/object_id_list", gconf.VALUE_STRING, objects)
    poll (main_loop)

    client.set_int ("/apps/panel/toplevels/foo/hide_delay", 5)
    poll (main_loop)

    time.sleep (3)

    # Remove the menu bar again
    while "foo" in objects:
        objects.remove ("foo")
    client.set_list ("/apps/panel/general/object_id_list", gconf.VALUE_STRING, objects)
    poll (main_loop)
    
    # Remove the clock again
    while "foo" in applets:
        applets.remove ("foo")
    client.set_list ("/apps/panel/general/applet_id_list", gconf.VALUE_STRING, applets)
    poll (main_loop)
    
    # Remove the panel again
    while "foo" in toplevels:
        toplevels.remove ("foo")
    client.set_list ("/apps/panel/general/toplevel_id_list", gconf.VALUE_STRING, toplevels)
    poll (main_loop)

    # Set random uninterpreted key back again
    client.set_bool ("/apps/panel/general/show_program_list", show_program_list)
    poll (main_loop)
    
    # Shutdown the client again
    client.notify_remove (notify_id)
    client.remove_dir ("/apps/panel")
    
    # Bye, bye cruft
    os.system ("gconftool-2 --recursive-unset /apps/panel/toplevels/foo")
    os.system ("gconftool-2 --recursive-unset /apps/panel/objects/foo")
    os.system ("gconftool-2 --recursive-unset /apps/panel/applets/foo")

    assert len (changes) == 9
    for change in changes:
        assert isinstance (change, userprofile.ProfileChange)
    for change in changes[1:4] + changes[5:8]:
        assert isinstance (change, PanelChange)
        assert change.id == "foo"
    for change in changes[-1:1]:
        assert isinstance (change, gconfsource.GConfChange)
        assert change.entry.key == "/apps/panel/general/show_program_list"
    assert isinstance (changes[1], PanelAddedChange)
    assert isinstance (changes[2], PanelAppletAddedChange)
    assert isinstance (changes[3], PanelObjectAddedChange)
    assert isinstance (changes[4], gconfsource.GConfChange)
    assert changes[4].entry.key == "/apps/panel/toplevels/foo/hide_delay"
    assert isinstance (changes[5], PanelObjectRemovedChange)
    assert isinstance (changes[6], PanelAppletRemovedChange)
    assert isinstance (changes[7], PanelRemovedChange)
