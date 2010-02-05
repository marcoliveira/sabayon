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
import gconf
import gconfsource
import subprocess
import bonobo
import xdg.DesktopEntry

try:
    import userprofile
    import util
    from config import *
    import debuglog
except:
    from sabayon import userprofile
    from sabayon import util
    from sabayon.config import *
    from sabayon import debuglog

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_PANEL_DELEGATE, fmt % args)

PANEL_LAUNCHER_DIR = ".gnome2/panel2.d/default/launchers"

def copy_dir (src_client, dst_client, dst_address, dir):
    for entry in src_client.all_entries (dir):
        schema_name = entry.get_schema_name ()
        if schema_name:
            gconfsource.associate_schema (dst_address, entry.key, schema_name)
        if entry.value and not entry.get_is_default ():
            dst_client.set (entry.key, entry.value)
    for subdir in src_client.all_dirs (dir):
        copy_dir (src_client, dst_client, dst_address, subdir)

class PanelChange (userprofile.ProfileChange):
    def __init__ (self, source, delegate, id):
        userprofile.ProfileChange.__init__ (self, source, delegate)
        self.id = id
    def get_id (self):
        return self.id
    def commit_change (self, mandatory):
        pass

class PanelAddedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_short_description (self):
        return _("Panel '%s' added") % self.id
    
class PanelRemovedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_short_description (self):
        return _("Panel '%s' removed") % self.id

class PanelAppletAddedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_short_description (self):
        return _("Applet '%s' added" % self.id)
        # FIXME: This only works if panel object type is bonobo-applet. Are all applets bonobo-applets ?
        # FIXME: Race condition with the code below.
        # panel_applet = self.delegate.PanelApplet(self.delegate, self.id)
        # toplevel_id = panel_applet.toplevel_id
        # name = panel_applet.name

        # panel_toplevel = self.delegate.PanelToplevel(self.delegate, toplevel_id)
        # panel_orientation = panel_toplevel.orientation

        # if panel_orientation == "top":
        #     return _("Applet %s added to top panel") % name
        # elif panel_orientation == "bottom":
        #     return _("Applet %s added to bottom panel") % name
        # elif panel_orientation == "left":
        #     return _("Applet %s added to left panel") % name
        # else:
        #     return _("Applet %s added to right panel") % name

class PanelAppletRemovedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_short_description (self):
        return _("Applet '%s' removed" % self.id)
        # FIXME: This only works if panel object type is bonobo-applet. Are all applets bonobo-applets ?
        # FIXME: Race condition with the code below.
        # panel_applet = self.delegate.PanelApplet(self.delegate, self.id)
        # toplevel_id = panel_applet.toplevel_id
        # name = panel_applet.name

        # panel_toplevel = self.delegate.PanelToplevel(self.delegate, toplevel_id)
        # panel_orientation = panel_toplevel.orientation

        # if panel_orientation == "top":
        #     return _("Applet %s removed from top panel") % name
        # elif panel_orientation == "bottom":
        #     return _("Applet %s removed from bottom panel") % name
        # elif panel_orientation == "left":
        #     return _("Applet %s removed from left panel") % name
        # else:
        #     return _("Applet %s removed from right panel") % name

class PanelObjectAddedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_short_description (self):
        return _("Object '%s' added" % self.id)
        # FIXME: Race condition with code below.
        # panel_object = self.delegate.PanelObject(self.delegate, self.id)
        # toplevel_id = panel_object.toplevel_id
        # name = panel_object.name

        # panel_toplevel = self.delegate.PanelToplevel(self.delegate, toplevel_id)
        # panel_orientation = panel_toplevel.orientation

        # if panel_orientation == "top":
        #     return _("%s added to top panel") % name
        # elif panel_orientation == "bottom":
        #     return _("%s added to bottom panel") % name
        # elif panel_orientation == "left":
        #     return _("%s added to left panel") % name
        # else:
        #     return _("%s added to right panel") % name

    def commit_change (self, mandatory):
        # Might have to commit a launcher file
        launcher = self.delegate.get_gconf_client ().get_string (PANEL_KEY_BASE + "/objects/" + self.id + "/launcher_location")
        if launcher and launcher[0] != '/':
            file = PANEL_LAUNCHER_DIR + "/" + launcher
            self.source.storage.add (file, self.delegate.home_dir, self.delegate.name)
    
class PanelObjectRemovedChange (PanelChange):
    def __init__ (self, source, delegate, id):
        PanelChange.__init__ (self, source, delegate, id)
    def get_short_description (self):
        return _("Object '%s' removed" % self.id)
        # FIXME: Race condition with code below.
        # panel_object = self.delegate.PanelObject(self.delegate, self.id)
        # toplevel_id = panel_object.toplevel_id
        # name = panel_object.name

        # panel_toplevel = self.delegate.PanelToplevel(self.delegate, toplevel_id)
        # panel_orientation = panel_toplevel.orientation

        # if panel_orientation == "top":
        #     return _("%s removed from top panel") % name
        # elif panel_orientation == "bottom":
        #     return _("%s removed from bottom panel") % name
        # elif panel_orientation == "left":
        #     return _("%s removed from left panel") % name
        # else:
        #     return _("%s removed from right panel") % name

    def commit_change (self, mandatory):
        launcher = self.delegate.get_gconf_client ().get_string (PANEL_KEY_BASE + "/objects/" + self.id + "/launcher_location")
        if launcher and launcher[0] != '/':
            file = PANEL_LAUNCHER_DIR + "/" + launcher
            self.source.storage.remove (file)

class PanelDelegate (userprofile.SourceDelegate):
    class PanelThing:
        def __init__ (self, delegate, id, added, removed):
            self.delegate     = delegate
            self.id           = id
            self.added        = added
            self.removed      = removed
            self.gconf_client = self.delegate.get_gconf_client ()
            self.SORTPRIORITY = 60
    
        def _copy_tree (self, dir):
            if not self.gconf_client.dir_exists(dir):
                (src_client, src_address) = gconfsource.get_client_and_address_for_path (os.path.join (util.get_home_dir (), '.gconf'))
                (dst_client, dst_address) = gconfsource.get_client_and_address_for_path (os.path.join (util.get_home_dir (), GCONF_DEFAULTS_SOURCE))
                copy_dir (src_client, dst_client, dst_address, dir)

    class PanelToplevel (PanelThing):
        def __init__ (self, delegate, id, added = False, removed = False):
            PanelDelegate.PanelThing.__init__ (self, delegate, id, added, removed)

            self._copy_tree (PANEL_KEY_BASE + "/toplevels/" + id)

            self.orientation = self.gconf_client.get_string (PANEL_KEY_BASE + "/toplevels/" + id + "/orientation")
            
            # FIXME: which of the following attributes do we really need?
            # self.name        = self.gconf_client.get_string (PANEL_KEY_BASE + "/toplevels/" + toplevel_id + "/name")
            # self.expand      = self.gconf_client.get_bool   (PANEL_KEY_BASE + "/toplevels/" + toplevel_id + "/expand")

    class PanelApplet (PanelThing):
        def __init__ (self, delegate, id, added = False, removed = False):
            PanelDelegate.PanelThing.__init__ (self, delegate, id, added, removed)

            self._copy_tree (PANEL_KEY_BASE + "/applets/" + id)
 
            toplevel_key_name = PANEL_KEY_BASE + "/applets/" + id + "/toplevel_id"
            bonobo_iid_key_name = PANEL_KEY_BASE + "/applets/" + id + "/bonobo_iid"

            self.toplevel_id = self.gconf_client.get_string (toplevel_key_name)
            self.bonobo_iid  = self.gconf_client.get_string (bonobo_iid_key_name)

            dprint ("Creating PanelApplet for '%s' (toplevel_key %s, toplevel_id %s, bonobo_key %s, bonobo_iid %s)",
                    id,
                    toplevel_key_name, self.toplevel_id,
                    bonobo_iid_key_name, self.bonobo_iid)
            
            if self.bonobo_iid:
                applet = bonobo.activation.query("iid == '" + self.bonobo_iid + "'" )
                for i in applet:
                    for prop in i.props:
                        if prop.name == "name":
                            self.name = prop.v.value_string #FIXME: This probably won't return localised names



    class PanelObject (PanelThing):
        def __init__ (self, delegate, id, added = False, removed = False):
            PanelDelegate.PanelThing.__init__ (self, delegate, id, added, removed)
  
            self._copy_tree (PANEL_KEY_BASE + "/objects/" + id)

            self.toplevel_id = self.gconf_client.get_string (PANEL_KEY_BASE + "/objects/" + id + "/toplevel_id")
            self.object_type = self.gconf_client.get_string (PANEL_KEY_BASE + "/objects/" + id + "/object_type")

            if self.object_type == "drawer-object":
                # Translators: This is a drawer in gnome-panel (where you can put applets)
                self.name = _("Drawer")
            elif self.object_type == "menu-object":
                self.name = _("Main Menu")
            elif self.object_type == "launcher-object":
                launcher_location = self.gconf_client.get_string (PANEL_KEY_BASE + "/objects/" + id + "/launcher_location")
                if launcher_location[0] == '/':
                    desktop_file = launcher_location
                elif launcher_location[0:7] == "file://": # See what happens when you drag and drop from the menu
                    desktop_file = launcher_location[7:]
                else:
                    desktop_file = PANEL_LAUNCHER_DIR + "/" + launcher_location
                launcher = xdg.DesktopEntry.DesktopEntry(desktop_file)
                self.name = _("%s launcher") % launcher.getName()
            elif self.object_type == "action-applet":
                action_type = self.gconf_client.get_string (PANEL_KEY_BASE + "/objects/" + id + "/action_type")
                if action_type == "lock":
                    self.name = _("Lock Screen button")
                elif action_type == "logout":
                    self.name = _("Logout button")
                elif action_type == "run":
                    self.name = _("Run Application button")
                elif action_type == "search":
                    self.name = _("Search button")
                elif action_type == "force-quit":
                    self.name = _("Force Quit button")
                elif action_type == "connect-server":
                    self.name = _("Connect to Server button")
                elif action_type == "shutdown":
                    self.name = _("Shutdown button")
                elif action_type == "screenshot":
                    self.name = _("Screenshot button")
                    
                else:
                    self.name = _("Unknown")
            else:
                self.name = _("Menu Bar")

    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, _("Panel"), source, PANEL_KEY_BASE)

        self.home_dir = util.get_home_dir()
        self.toplevels = {}
        self.applets = {}
        self.objects = {}

    def get_gconf_client (self):
        return self.source.gconf_client

    def __read_panel_config (self):
        dprint ("Reading initial panel config");
        
        dprint ("Toplevels:");
        for id in self.get_gconf_client ().get_list (PANEL_KEY_BASE + "/general/toplevel_id_list", gconf.VALUE_STRING):
            if not self.toplevels.has_key (id):
                dprint ("  %s", id);
                self.toplevels[id] = PanelDelegate.PanelToplevel (self, id)
                
        dprint ("Applets:");
        for id in self.get_gconf_client ().get_list (PANEL_KEY_BASE + "/general/applet_id_list", gconf.VALUE_STRING):
            if not self.applets.has_key (id):
                dprint ("  %s", id);
                self.applets[id] = PanelDelegate.PanelApplet (self, id)
                
        dprint ("Objects:");
        for id in self.get_gconf_client ().get_list (PANEL_KEY_BASE + "/general/object_id_list", gconf.VALUE_STRING):
            if not self.objects.has_key (id):
                dprint ("  %s", id);
                self.objects[id] = PanelDelegate.PanelObject (self, id)

    def __handle_id_list_change (self, change, dict, thing_class, added_class, removed_class):
        if not change.value or \
               change.value.type != gconf.VALUE_LIST or \
               change.value.get_list_type () != gconf.VALUE_STRING:
                return True

        id_list = []
        for v in change.value.get_list ():
            id_list.append (v.get_string ())
            
        added = []
        for id in id_list:
            if dict.has_key (id) and not dict[id].removed:
                continue
            if not dict.has_key (id):
                dict[id] = thing_class (self, id, True)
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

        dprint ("%s changed: (%s) added, (%s) removed\n",
                change.key, added, removed);

        for id in added:
            self.source.emit ("changed", added_class (self.source, self, id))
        for id in removed:
            self.source.emit ("changed", removed_class (self.source, self, id))

        return True

    def handle_change (self, change):
        if change.key.startswith (PANEL_KEY_BASE + "/toplevels/"):
            toplevel_id = change.key.split ("/")[4]
            if not self.toplevels.has_key (toplevel_id) or \
               self.toplevels[toplevel_id].added or \
               self.toplevels[toplevel_id].removed:
                return True
        
        elif change.key.startswith (PANEL_KEY_BASE + "/objects/"):
            object_id = change.key.split ("/")[4]
            if not self.objects.has_key (object_id) or \
               self.objects[object_id].added or \
               self.objects[object_id].removed:
                return True
        
        elif change.key.startswith (PANEL_KEY_BASE + "/applets"):
            applet_id = change.key.split ("/")[4]
            if not self.applets.has_key (applet_id) or \
               self.applets[applet_id].added or \
               self.applets[applet_id].removed:
                return True
        
        elif change.key == PANEL_KEY_BASE + "/general/toplevel_id_list":
            return self.__handle_id_list_change (change,
                                                 self.toplevels,
                                                 PanelDelegate.PanelToplevel,
                                                 PanelAddedChange,
                                                 PanelRemovedChange)
            
        elif change.key == PANEL_KEY_BASE + "/general/applet_id_list":
            return self.__handle_id_list_change (change,
                                                 self.applets,
                                                 PanelDelegate.PanelApplet,
                                                 PanelAppletAddedChange,
                                                 PanelAppletRemovedChange)
            
        elif change.key == PANEL_KEY_BASE + "/general/object_id_list":
            return self.__handle_id_list_change (change,
                                                 self.objects,
                                                 PanelDelegate.PanelObject,
                                                 PanelObjectAddedChange,
                                                 PanelObjectRemovedChange)

        return False

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

        change.commit_change (mandatory)

        (client, address) = self.source.get_committing_client_and_address (mandatory)

        copy_dir (self.get_gconf_client (), client, address, PANEL_KEY_BASE + "/" + dir_name + "/" + thing.id)

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

        change.commit_change (mandatory)

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

    def get_path_description (self, path):
        return "Panel launcher: %s"%os.path.basename(path)
    
    def start_monitoring (self):
        # Need to do this here so gconf paths are setup
        self.__read_panel_config ()
        pass

    def stop_monitoring (self):
        """Stop monitoring for configuration changes."""
        # Nothing to do here
        pass

    def sync_changes (self):
        # Nothing to do here
        pass
    
    def set_enforce_mandatory (self, enforce):
        # Nothing to do here
        pass

    def __apply_foreach (self, source, path):
        self.source.storage.extract (path, self.home_dir)

    def apply (self, is_sabayon_session):
        self.source.storage.foreach (self.__apply_foreach, source = self.name)
        pass

def get_gconf_delegate (source):
    return PanelDelegate (source)

class PanelFileDelegate (userprofile.SourceDelegate):
    def __init__ (self, source):
        userprofile.SourceDelegate.__init__ (self, _("Panel File"), source, PANEL_LAUNCHER_DIR)

    def handle_change (self, change):
        dprint ("Ignoring file chage due to panel delegation: %s"%change)
        return True

    def start_monitoring (self):
        pass

    def stop_monitoring (self):
        pass

    def sync_changes (self):
        pass

    def set_enforce_mandatory (self, enforce):
        pass

    def apply (self, is_sabayon_session):
        pass

def get_files_delegate(source):
    return PanelFileDelegate(source)


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
    subprocess.call (["gconftool-2", "--recursive-unset", "%s/toplevels/foo" % PANEL_KEY_BASE])
    subprocess.call (["gconftool-2", "--recursive-unset", "%s/objects/foo" % PANEL_KEY_BASE])
    subprocess.call (["gconftool-2", "--recursive-unset", "%s/applets/foo" % PANEL_KEY_BASE])
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
                    (client, address) = gconfsource.get_client_and_address_for_path (
                        os.path.join (self.temp_path, GCONF_DEFAULTS_SOURCE))
                    self.defaults_client = client
                    self.defaults_address = address
                return (self.defaults_client, self.defaults_address)
            else:
                if not self.mandatory_client:
                    (client, address) = gconfsource.get_client_and_address_for_path (
                        os.path.join (self.temp_path, GCONF_MANDATORY_SOURCE))
                    self.mandatory_client = client
                    self.mandatory_address = address
                return (self.mandatory_client, self.mandatory_address)
    gobject.type_register (TempSource)
    source = TempSource (temp_path)

    # Set up the client
    def handle_notify (client, cnx_id, entry, source):
        source.emit_change (gconfsource.GConfChange (source, entry.key, entry.value))
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
    assert changes[0].key == PANEL_KEY_BASE + "/general/show_program_list"
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
    
    subprocess.call (["gconftool-2", "--shutdown"])
    time.sleep (1)

    assert os.access (os.path.join (temp_path, GCONF_DEFAULTS_SOURCE + "/apps/panel/general/%gconf.xml"), os.F_OK)
    assert os.access (os.path.join (temp_path, GCONF_DEFAULTS_SOURCE + "/apps/panel/toplevels/foo/%gconf.xml"), os.F_OK)

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
    assert changes[3].key == PANEL_KEY_BASE + "/general/show_program_list"

    (
        PANEL_OBJECT_REMOVED,
        PANEL_APPLET_REMOVED,
        PANEL_REMOVED
    ) = range (3)
    
    assert isinstance (changes[PANEL_OBJECT_REMOVED], PanelObjectRemovedChange)
    assert isinstance (changes[PANEL_APPLET_REMOVED], PanelAppletRemovedChange)
    assert isinstance (changes[PANEL_REMOVED], PanelRemovedChange)

    source.commit_change (changes[PANEL_REMOVED], False)

    dprint ("Committed changes to %s", temp_path)
    subprocess.call (["gconftool-2", "--shutdown"])
    time.sleep (1)
    
    assert not os.access (os.path.join (temp_path, GCONF_DEFAULTS_SOURCE + "/apps/panel/toplevels/foo/%gconf.xml"), os.F_OK)

    # Bye, bye cruft
    subprocess.call (["gconftool-2", "--recursive-unset", "%s/toplevels/foo" % PANEL_KEY_BASE])
    subprocess.call (["gconftool-2", "--recursive-unset", "%s/objects/foo" % PANEL_KEY_BASE])
    subprocess.call (["gconftool-2", "--recursive-unset", "%s/applets/foo" % PANEL_KEY_BASE])

    shutil.rmtree (temp_path, True)
