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

import os.path
import shutil
import tempfile
import time
import locale
import gtk
import userprofile
import util
import aboutdialog
import saveconfirm
import gconfviewer
import fileviewer
from config import *
import debuglog
import errors

_ui_string = '''
<ui>
  <menubar name="Menubar">
    <menu action="ProfileMenu">
      <menuitem action="Save"/>
      <separator/>
      <menuitem action="Close"/>
    </menu>
    <menu action="EditMenu">
      <menuitem action="Delete"/>
    </menu>
    <menu action="HelpMenu">
      <menuitem action="Contents"/>
      <menuitem action="About"/>
    </menu>
  </menubar>
</ui>
'''

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL, fmt % args)

class ProfileModel (gtk.ListStore):
    (
        COLUMN_SOURCE,
        COLUMN_PATH,
        COLUMN_DESCRIPTION
    ) = range (3)

    def __init__ (self, profile):
        gtk.ListStore.__init__ (self, str, str, str)

        self.profile = profile
        self.reload ()

    def reload (self):
        dprint ("Reloading profile model")
        self.clear ()
        for (source_name, path) in self.profile.storage.list ():
            source = self.profile.get_source (source_name)
            if source is None:
                source = self.profile.get_delegate (source_name)
            
            dprint ("  source %s, path %s, description %s",
                    source_name,
                    path,
                    source.get_path_description (path))
            
            self.set (self.prepend (),
                      self.COLUMN_SOURCE,          source_name,
                      self.COLUMN_PATH,            path,
                      self.COLUMN_DESCRIPTION,     source.get_path_description (path))


class ProfileEditorWindow:
    def __init__ (self, profile_name, parent_window):
        self.profile_name = profile_name
        self.profile = userprofile.UserProfile (profile_name)
        self.storage = self.profile.storage
        self.last_save_time = 0

        self.window = gtk.Window (gtk.WINDOW_TOPLEVEL)
        self.window.set_title (_("Profile %s")%profile_name)
        self.window.set_icon_name ("sabayon")
        self.window.set_transient_for (parent_window)
        self.window.set_destroy_with_parent (True)
        self.window.set_default_size (480, 380)
        self.window.connect ("delete-event",
                             self.__handle_delete_event);

        self.main_vbox = gtk.VBox (False, 0)
        self.main_vbox.show ()
        self.window.add (self.main_vbox)

        self.__setup_menus ()

        self.scrolled = gtk.ScrolledWindow ()
        self.scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.set_shadow_type (gtk.SHADOW_IN)
        self.scrolled.show ()
        self.main_vbox.pack_start (self.scrolled, True, True, 0)
        
        self.__setup_treeview ()

        self.window.show ()

        self.__set_needs_saving (False)

    def __reload_models (self):
        self.profile_model.reload ()
        dprint ("Reloaded models")

    def __set_needs_saving (self, needs_saving):
        if needs_saving:
            if not self.last_save_time:
                self.last_save_time = int (time.time ())
            self.save_action.set_sensitive (True)
        else:
            self.last_save_time = 0
            self.save_action.set_sensitive (False)
        self.__reload_models ()

    def __delete_currently_selected (self):
        (model, row) = self.treeview.get_selection ().get_selected ()
        if not row:
            return
    
        dprint ("Deleting '%s'", model[row][ProfileModel.COLUMN_PATH])

        self.storage.remove (model[row][ProfileModel.COLUMN_PATH])
        self.__set_needs_saving (True)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_key_press (self, treeview, event):
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete):
            self.__delete_currently_selected ()
        
    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_save (self, action):
        self.storage.save ()
        self.__set_needs_saving (False)

    def __do_saveconfirm (self):
        if self.last_save_time:
            dialog = saveconfirm.SaveConfirmationAlert (self.window,
                                                        self.profile_name,
                                                        time.time () - self.last_save_time)
            response = dialog.run ()
            dialog.destroy ()

            if response == gtk.RESPONSE_CANCEL:
                return False
            if response == gtk.RESPONSE_YES:
                self.storage.save ()
                self.__set_needs_saving (False)
        
        return True
        
    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_close (self, action):
        if self.__do_saveconfirm ():
            self.window.destroy ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_delete_event (self, window, event):
        return not self.__do_saveconfirm ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_delete (self, action):
        self.__delete_currently_selected ()
        
    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_help (self, action):
        try:
            gtk.show_uri (None, "ghelp:sabayon", gtk.get_current_event_time())
        except gobject.GError, e:
            pass

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_about (self, action):
        aboutdialog.show_about_dialog (self.window)

    def __add_widget (self, ui_manager, widget):
        self.main_vbox.pack_start (widget, False, False, 0)
        
    def __setup_menus (self):
        actions = [
            ("ProfileMenu", None, _("_Profile")),
            ("Save", gtk.STOCK_SAVE, _("_Save"), "<control>S", _("Save profile"), self.__handle_save),
            ("Close", gtk.STOCK_CLOSE, _("_Close"), "<control>W", _("Close the current window"), self.__handle_close),
            ("EditMenu", None, _("_Edit")),
            ("Delete", gtk.STOCK_DELETE, _("_Delete"), "<control>D", _("Delete item"), self.__handle_delete),
            ("HelpMenu", None, _("_Help")),
            ("Contents", gtk.STOCK_HELP, _("_Contents"), None, _("Help Contents"), self.__handle_help),
            ("About", gtk.STOCK_ABOUT, _("_About"), None, _("About Sabayon"), self.__handle_about),
        ]
        action_group = gtk.ActionGroup ("WindowActions")
        action_group.add_actions (actions)
        
        self.ui_manager = gtk.UIManager ()
        self.ui_manager.insert_action_group (action_group, 0)
        self.ui_manager.connect ("add-widget", self.__add_widget)
        self.ui_manager.add_ui_from_string (_ui_string)
        self.ui_manager.ensure_update ()

        self.window.add_accel_group (self.ui_manager.get_accel_group ())

        self.save_action = action_group.get_action ("Save")
        self.delete_action = action_group.get_action ("Delete")

    def __setup_treeview (self):
        self.profile_model = ProfileModel (self.profile)
        
        self.treeview = gtk.TreeView (self.profile_model)
        self.treeview.show ()
        self.scrolled.add (self.treeview)
        
        self.treeview.get_selection ().set_mode (gtk.SELECTION_SINGLE)
        self.treeview.get_selection ().connect ("changed",
                                                self.__treeview_selection_changed)

        self.treeview.set_headers_visible (False)

        c = gtk.TreeViewColumn (_("Description"),
                                gtk.CellRendererText (),
                                text = ProfileModel.COLUMN_DESCRIPTION)
        self.treeview.append_column (c)

        self.treeview.connect ("key-press-event", self.__handle_key_press)
        self.treeview.connect ("row-activated",   self.__handle_row_activation)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __treeview_selection_changed (self, selection):
        (model, row) = selection.get_selected ()
        if not row:
            self.delete_action.set_sensitive (False)
            return

        dprint ("Selected '%s'", model[row][ProfileModel.COLUMN_PATH])

        self.delete_action.set_sensitive (True)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_row_activation (self, treeview, tree_path, column):
        iter = self.profile_model.get_iter (tree_path)
        path = self.profile_model[iter][ProfileModel.COLUMN_PATH]
        description = self.profile_model[iter][ProfileModel.COLUMN_DESCRIPTION]
        source_name = self.profile_model[iter][ProfileModel.COLUMN_SOURCE]
        
        dprint ("Activating '%s'", path)
        
        extract_dir = tempfile.mkdtemp (prefix = "sabayon-temp-")
        self.storage.extract (path, extract_dir)
        extracted_path = os.path.join (extract_dir, path)

        if source_name == _("GConf"):
            viewer = gconfviewer.GConfViewer (extracted_path, description, self.window)
            viewer.connect ("destroy", lambda v, dir: shutil.rmtree (dir, True), extract_dir)
            viewer.show ()
        elif source_name == _("Files") or source_name == _("Panel"):
            if os.path.isfile(extracted_path):
                viewer = fileviewer.FileViewer (extracted_path, description, self.window)
                viewer.connect ("destroy", lambda v, dir: shutil.rmtree (dir, True), extract_dir)
                viewer.show ()
        else:
            shutil.rmtree (extract_dir, True)
