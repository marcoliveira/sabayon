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

import gtk
import gtk.glade
import storage
import util
import aboutdialog
import saveconfirm
import time
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

  <toolbar name="Toolbar">
    <toolitem action="Save"/>
    <separator/>
    <toolitem action="Delete"/>
  </toolbar>
</ui>
'''

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class ProfileModel (gtk.ListStore):
    (
        COLUMN_NAME,
        COLUMN_BITE_ME_GUIDO
    ) = range (2)

    def __init__ (self, storage):
        gtk.ListStore.__init__ (self, str)

        self.storage = storage
        self.reload ()

    def reload (self):
        self.clear ()
        for (source, name) in self.storage.list ():
            row = self.prepend ()
            self.set (row,
                      self.COLUMN_NAME, name)

class ProfileEditorWindow:
    def __init__ (self, profile_name, parent_window):
        self.profile_name = profile_name
        self.storage = storage.ProfileStorage (profile_name)
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

        self.__setup_menus_and_toolbar ()

        self.scrolled = gtk.ScrolledWindow ()
        self.scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.show ()
        self.main_vbox.pack_start (self.scrolled, True, True, 0)
        
        self.__setup_treeview ()

        self.window.show ()

        self.__set_needs_saving (False)

    def __set_needs_saving (self, needs_saving):
        if needs_saving:
            if not self.last_save_time:
                self.last_save_time = int (time.time ())
            self.save_action.set_sensitive (True)
        else:
            self.last_save_time = 0
            self.save_action.set_sensitive (False)

    def __delete_currently_selected (self):
        (model, row) = self.treeview.get_selection ().get_selected ()
        if not row:
            return
    
        dprint ("Deleting '%s'", model[row][ProfileModel.COLUMN_NAME])

        self.storage.remove (model[row][ProfileModel.COLUMN_NAME])
        self.profile_model.reload ()
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
        
    def __setup_menus_and_toolbar (self):
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

    def __setup_treeview (self):
        self.profile_model = ProfileModel (self.storage)
        
        self.treeview = gtk.TreeView (self.profile_model)
        self.treeview.show ()
        self.scrolled.add (self.treeview)
        
        self.treeview.get_selection ().set_mode (gtk.SELECTION_SINGLE)
        self.treeview.get_selection ().connect ("changed", self.__treeview_selection_changed)

        self.treeview.set_headers_visible (False)

        c = gtk.TreeViewColumn (_("Name"),
                                gtk.CellRendererText (),
                                text = ProfileModel.COLUMN_NAME)
        self.treeview.append_column (c)
        
        self.treeview.connect ("key-press-event", self.__handle_key_press)

    def __treeview_selection_changed (self, selection):
        (model, row) = selection.get_selected ()
        if not row:
            self.delete_action.set_sensitive (False)
            return

        dprint ("Selected '%s'", model[row][ProfileModel.COLUMN_NAME])

        self.delete_action.set_sensitive (True)
