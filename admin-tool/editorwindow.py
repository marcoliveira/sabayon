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

import os.path
import shutil
import tempfile
import time
import locale
import gtk
import gtk.glade
import userprofile
import util
import aboutdialog
import saveconfirm
import gconfviewer
import fileviewer
from config import *

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
      <separator/>
      <menuitem action="ClearHistory"/>
    </menu>
    <menu action="HelpMenu">
      <menuitem action="About"/>
    </menu>
  </menubar>
</ui>
'''

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class ProfileModel (gtk.ListStore):
    (
        COLUMN_SOURCE,
        COLUMN_PATH,
        COLUMN_DESCRIPTION,
        COLUMN_REVISION,
        COLUMN_REVISIONS_MODEL
    ) = range (5)

    def __init__ (self, profile):
        gtk.ListStore.__init__ (self, str, str, str, str, RevisionsModel)

        self.profile = profile
        self.reload ()

    def reload (self):
        dprint ("Reloading profile model")
        self.clear ()
        for (source_name, path) in self.profile.storage.list ():
            source = self.profile.get_source (source_name)
            
            revisions_model = RevisionsModel (self.profile.storage, path)
            first_revision = revisions_model.get_iter_first ()
            
            self.set (self.prepend (),
                      self.COLUMN_SOURCE,          source_name,
                      self.COLUMN_PATH,            path,
                      self.COLUMN_DESCRIPTION,     source.get_path_description (path),
                      self.COLUMN_REVISION,        revisions_model[first_revision][RevisionsModel.COLUMN_DATE],
                      self.COLUMN_REVISIONS_MODEL, revisions_model)

class RevisionsModel (gtk.ListStore):
    (
        COLUMN_REVISION,
        COLUMN_DATE
    ) = range (2)

    def __init__ (self, storage, path = None):
        gtk.ListStore.__init__ (self, str, str)

        self.storage = storage
        self.path = path
        self.time_format = locale.nl_langinfo (locale.D_T_FMT)
        self.reload ()

    def reload (self):
        dprint ("Reloading revisions model")
        self.clear ()
        iter = None
        revisions = self.storage.get_revisions (self.path)
        revisions.reverse ()
        for (revision, timestamp) in revisions:
            self.set (self.prepend (),
                      self.COLUMN_REVISION, revision,
                      self.COLUMN_DATE,     time.strftime (self.time_format,
                                                           time.localtime (float (timestamp))))

class ProfileEditorWindow:
    def __init__ (self, profile_name, parent_window):
        self.profile_name = profile_name
        self.profile = userprofile.UserProfile (profile_name)
        self.storage = self.profile.storage
        self.last_save_time = 0

        self.window = gtk.Window (gtk.WINDOW_TOPLEVEL)
        self.window.set_title (_("All Your Settings Are Belong To Us"))
        self.window.set_icon_name ("sabayon")
        self.window.set_transient_for (parent_window)
        self.window.set_destroy_with_parent (True)
        self.window.set_default_size (480, 380)

        self.main_vbox = gtk.VBox (False, 0)
        self.main_vbox.show ()
        self.window.add (self.main_vbox)

        self.__setup_menus ()
        self.__setup_profile_revisions_combo ()

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
        
        self.revisions_model.reload ()
        if self.current_revision:
            iter = self.revisions_model.get_iter_first ()
            while iter:
                if self.revisions_model[iter][RevisionsModel.COLUMN_REVISION] == self.current_revision:
                    self.revisions_combo.set_active_iter (iter)
                    break
                iter = self.revisions_model.iter_next (iter)
        else:
            iter = self.revisions_model.get_iter_first ()
            self.current_revision = self.revisions_model[iter][RevisionsModel.COLUMN_REVISION]
            self.revisions_combo.set_active_iter (iter)

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

    def __handle_key_press (self, treeview, event):
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete):
            self.__delete_currently_selected ()
        
    def __handle_save (self, action):
        self.storage.save ()
        self.__set_needs_saving (False)

    def __handle_close (self, action):
        if self.last_save_time:
            dialog = saveconfirm.SaveConfirmationAlert (self.window,
                                                        self.profile_name,
                                                        time.time () - self.last_save_time)
            response = dialog.run ()
            dialog.destroy ()

            if response == gtk.RESPONSE_CANCEL:
                return
            if response == gtk.RESPONSE_YES:
                self.storage.save ()
                self.__set_needs_saving (False)
        
        self.window.destroy ()

    def __handle_delete (self, action):
        self.__delete_currently_selected ()
        
    def __handle_clear_history (self, action):
        self.storage.clear_revisions ()
        self.__set_needs_saving (True)

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
            ("ClearHistory", gtk.STOCK_CLEAR, _("C_lear History"), None, _("Clear revision history"), self.__handle_clear_history),
            ("HelpMenu", None, _("_Help")),
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

    def __profile_revision_changed (self, combo):
        revision = self.revisions_model[self.revisions_combo.get_active_iter ()][RevisionsModel.COLUMN_REVISION]
        if self.current_revision == revision:
            return
        dprint ("Profile revision changed: %s", revision)
        self.storage.revert (revision)
        self.current_revision = None
        self.__set_needs_saving (True)

    def __setup_profile_revisions_combo (self):
        hbox = gtk.HBox (False, 6)
        hbox.set_border_width (6)
        hbox.show ()
        self.main_vbox.pack_start (hbox, False, False, 0)

        label = gtk.Label (_("_Version:"))
        label.set_use_underline (True)
        label.set_alignment (0.0, 0.5)
        label.show ()
        hbox.pack_start (label, False, False, 0)
        
        self.revisions_model = RevisionsModel (self.storage)
        self.revisions_combo = gtk.ComboBox (self.revisions_model)
        self.revisions_combo.connect ("changed", self.__profile_revision_changed)
        self.revisions_combo.show ()

        renderer = gtk.CellRendererText ()
        self.revisions_combo.pack_start (renderer, False)
        self.revisions_combo.set_attributes (renderer, text = RevisionsModel.COLUMN_DATE)
        
        label.set_mnemonic_widget (self.revisions_combo)
        hbox.pack_start (self.revisions_combo, True, True, 0)

        iter = self.revisions_model.get_iter_first ()
        self.current_revision = self.revisions_model[iter][RevisionsModel.COLUMN_REVISION]
        self.revisions_combo.set_active_iter (iter)
        
    def __file_revision_changed (self, cell, tree_path, new_text):
        iter = self.profile_model.get_iter_from_string (tree_path)
        path = self.profile_model[iter][ProfileModel.COLUMN_PATH]
        revisions_model = self.profile_model[iter][ProfileModel.COLUMN_REVISIONS_MODEL]

        revision_iter = revisions_model.get_iter_first ()
        while revision_iter:
            if revisions_model[revision_iter][RevisionsModel.COLUMN_DATE] == new_text:
                revision = revisions_model[revision_iter][RevisionsModel.COLUMN_REVISION]
                dprint ("New file revision for '%s': '%s'", path, revision)
                self.profile_model.set (iter, ProfileModel.COLUMN_REVISION, revision)
                self.storage.revert (revision, path)
                self.current_revision = None
                self.__set_needs_saving (True)
                return
            revision_iter = revisions_model.iter_next (revision_iter)
        
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

        renderer = gtk.CellRendererCombo ()
        renderer.set_property ("text-column", RevisionsModel.COLUMN_DATE)
        renderer.set_property ("editable", True)
        renderer.set_property ("has-entry", False)
        renderer.connect ("edited", self.__file_revision_changed)

        c = gtk.TreeViewColumn (_("Version"),
                                renderer,
                                model = ProfileModel.COLUMN_REVISIONS_MODEL,
                                text = ProfileModel.COLUMN_REVISION)
        self.treeview.append_column (c)

        self.treeview.connect ("key-press-event", self.__handle_key_press)
        self.treeview.connect ("row-activated",   self.__handle_row_activation)

    def __treeview_selection_changed (self, selection):
        (model, row) = selection.get_selected ()
        if not row:
            self.delete_action.set_sensitive (False)
            return

        dprint ("Selected '%s'", model[row][ProfileModel.COLUMN_PATH])

        self.delete_action.set_sensitive (True)

    def __handle_row_activation (self, treeview, tree_path, column):
        iter = self.profile_model.get_iter (tree_path)
        path = self.profile_model[iter][ProfileModel.COLUMN_PATH]
        source_name = self.profile_model[iter][ProfileModel.COLUMN_SOURCE]
        
        dprint ("Activating '%s'", path)
        
        extract_dir = tempfile.mkdtemp (prefix = "sabayon-temp-")
        self.storage.extract (path, extract_dir)
        extracted_path = os.path.join (extract_dir, path)

        if source_name == _("GConf"):
            viewer = gconfviewer.GConfViewer (extracted_path, self.window)
            viewer.connect ("destroy", lambda v, dir: shutil.rmtree (dir), extract_dir)
            viewer.show ()
        elif source_name == _("Files"):
            viewer = fileviewer.FileViewer (extracted_path, self.window)
            viewer.connect ("destroy", lambda v, dir: shutil.rmtree (dir), extract_dir)
            viewer.show ()
        else:
            shutil.rmtree (extract_dir)
