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

import time
import gobject
import gtk
import gtk.gdk
import pango
import util
import userprofile
import protosession
import changeswindow
import sessionwidget
import saveconfirm
import aboutdialog
from config import *

_ui_string = '''
<ui>
  <menubar name="Menubar">
    <menu action="ProfileMenu">
      <menuitem action="Save"/>
      <separator/>
      <menuitem action="Quit"/>
    </menu>
    <menu action="EditMenu">
      <menuitem action="Changes"/>
    </menu>
    <menu action="HelpMenu">
      <menuitem action="About"/>
    </menu>
  </menubar>
</ui>
'''

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class ProfileChangesModel (gtk.ListStore):
    __gsignals__ = {
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }
        
    (
        COLUMN_CHANGE,
        COLUMN_IGNORE,
        COLUMN_MANDATORY,
        COLUMN_LOCK_PIXBUF,
        COLUMN_DESCRIPTION
    ) = range (5)

    def __init__ (self, profile):
        gtk.ListStore.__init__ (self, userprofile.ProfileChange, bool, bool, gtk.gdk.Pixbuf, str, str)

        icon_theme = gtk.icon_theme_get_default ()

        self.locked_pixbuf   = icon_theme.load_icon ("stock_lock",      16, 0)
        self.unlocked_pixbuf = icon_theme.load_icon ("stock_lock-open", 16, 0)

        self.profile = profile
        self.profile.connect ("changed", self.handle_profile_change)

    def handle_profile_change (self, profile, new_change):
        mandatory = False
        ignore = False
        iter = self.get_iter_first ()
        while iter:
            next = self.iter_next (iter)
            change = self[iter][self.COLUMN_CHANGE]
            if change.get_source () == new_change.get_source () and \
               change.get_id ()     == new_change.get_id ():
                ignore    = self[iter][self.COLUMN_IGNORE]
                mandatory = self[iter][self.COLUMN_MANDATORY]
                self.remove (iter)
            iter = next

        if mandatory:
            lock_pixbuf = self.locked_pixbuf
        else:
            lock_pixbuf = self.unlocked_pixbuf

        row = self.prepend ()
        self.set (row,
                  self.COLUMN_CHANGE,      new_change,
                  self.COLUMN_IGNORE,      ignore,
                  self.COLUMN_MANDATORY,   mandatory,
                  self.COLUMN_LOCK_PIXBUF, lock_pixbuf,
                  self.COLUMN_DESCRIPTION, new_change.get_short_description ())
        self.emit ("changed")

    def clear (self):
        gtk.ListStore.clear (self)
        self.emit ("changed")

gobject.type_register (ProfileChangesModel)

class SessionWindow:
    def __init__ (self, profile_name, profile_path, display_number):
        self.profile_name   = profile_name
        self.profile_path   = profile_path
        self.display_number = display_number

        self.profile = userprofile.UserProfile (profile_path)

        self.changes_model = ProfileChangesModel (self.profile)
        self.changes_model.connect ("changed", self.__changes_model_changed)
        self.changes_window = None

        self.last_save_time = 0

        self.window = gtk.Window ()
        self.window.set_icon_name ("sabayon")
        self.window.connect ("delete-event",
                             self.__handle_delete_event);

        self.box = gtk.VBox ()
        self.window.add (self.box)
        self.box.show ()

        self.__setup_menus ()
        self.__setup_session ()
        self.__setup_statusbar ()

        self.__set_needs_saving (False)

        self.profile.start_monitoring ()
        
    def __add_widget (self, ui_manager, widget):
        self.box.pack_start (widget, False, False, 0)
        
    def __setup_menus (self):
        actions = [
            ("ProfileMenu", None,            _("_Profile")),
            ("Save",        gtk.STOCK_SAVE,  _("_Save"),    "<control>S", _("Save profile"),             self.__handle_save),
            ("Quit",        gtk.STOCK_QUIT,  _("_Quit"),    "<control>Q", _("Close the current window"), self.__handle_quit),
            ("EditMenu",    None,            _("_Edit")),
            ("Changes",     gtk.STOCK_EDIT,  _("_Changes"), "<control>H", _("Edit changes"),             self.__handle_edit),
            ("HelpMenu",    None,            _("_Help")),
            ("About",       gtk.STOCK_ABOUT, _("_About"),   None,         _("About Sabayon"),            self.__handle_about),
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
    
    def __set_needs_saving (self, needs_saving):
        if needs_saving:
            if not self.last_save_time:
                self.last_save_time = int (time.time ())
            self.save_action.set_sensitive (True)
        else:
            self.last_save_time = 0
            self.save_action.set_sensitive (False)
            
    def __changes_model_changed (self, model):
        self.__set_needs_saving (not model.get_iter_first () is None)
        
    def __do_save (self):
        iter = self.changes_model.get_iter_first ()
        while iter:
            change    = self.changes_model[iter][ProfileChangesModel.COLUMN_CHANGE]
            ignore    = self.changes_model[iter][ProfileChangesModel.COLUMN_IGNORE]
            mandatory = self.changes_model[iter][ProfileChangesModel.COLUMN_MANDATORY]

            if not ignore:
                dprint ("Committing: %s, mandatory = %s", change.get_id (), mandatory)
                try:
                    change.get_source ().commit_change (change, mandatory)
                except:
                    util.print_exception ()
                
            iter = self.changes_model.iter_next (iter)
        
        self.changes_model.clear ()
        self.profile.sync_changes ()

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
                self.__do_save ()
        
        return True
    
    def __handle_save (self, action):
        self.__do_save ()
        
    def __handle_quit (self, action):
        if self.__do_saveconfirm ():
            self.window.destroy ()

    def __handle_delete_event (self, window, event):
        return not self.__do_saveconfirm ()

    def __handle_about (self, action):
        aboutdialog.show_about_dialog (self.window)

    def __handle_edit (self, action):
        if not self.changes_window:
            self.changes_window = changeswindow.ChangesWindow (self.changes_model,
                                                               self.window)
            self.changes_window.window.connect ("delete-event",
                                                gtk.Widget.hide_on_delete)
        self.changes_window.window.present ()
    
    def __session_finished (self, session):
        self.window.destroy ()
        
    def __session_mapped (self, session_widget, event):
        dprint ("Session widget mapped; starting prototype session")
        self.session_widget.disconnect (self.mapped_handler_id)
        self.mapped_handler_id = 0
        self.session.connect ("finished", self.__session_finished)
        self.session.start (str (self.session_widget.session_window.xid))
        return False

    def __setup_session (self):
        self.session = protosession.ProtoSession (self.profile_name, self.display_number)

        screen = gtk.gdk.screen_get_default ()
        width  = (screen.get_width ()  * 3) / 4
        height = (screen.get_height () * 3) / 4

        dprint ("Creating %dx%d session wiget", width, height)
        
        self.session_widget = sessionwidget.SessionWidget (width, height)
        self.box.pack_start (self.session_widget, True, True)
        self.mapped_handler_id = self.session_widget.connect ("map-event", self.__session_mapped)
        self.session_widget.show ()

    def __update_statusbar (self, model):
        iter = self.changes_model.get_iter_first ()
        if iter:
            self.statusbar.pop (self.status_context_id)
            self.statusbar.push (self.status_context_id,
                                 self.changes_model[iter][self.changes_model.COLUMN_DESCRIPTION])

    def __update_resize_grip (self, window, event):
        if event.changed_mask & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            if event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED:
                self.statusbar.set_has_resize_grip (False)
            else:
                self.statusbar.set_has_resize_grip (True)

    def __setup_statusbar (self):
        self.statusbar = gtk.Statusbar ()
        self.box.pack_start (self.statusbar, False, False)
        self.statusbar.show ()

        self.status_context_id = self.statusbar.get_context_id ("sabayon-change")

        self.changes_model.connect ("changed", self.__update_statusbar)

        self.window.connect ("window-state-event", self.__update_resize_grip)
