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
import debuglog
import errors
from lockdownappliersabayon import LockdownApplierSabayon
from Pessulus import maindialog as lockdowndialog
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
      <menuitem action="Lockdown"/>
      <menuitem action="EnforceMandatory"/>
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

class ProfileChangesModel (gtk.ListStore):
    __gsignals__ = {
        "changed" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (userprofile.ProfileChange, ))
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


    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def handle_profile_change (self, profile, new_change):
        default_mandatory = False
        ignore = new_change.get_ignore_default ()
        iter = self.find (new_change.get_source (), new_change.get_id ())
        old_change = None
        if iter:
            ignore    = self[iter][self.COLUMN_IGNORE]
            default_mandatory = self[iter][self.COLUMN_MANDATORY]
            old_change = self[iter][self.COLUMN_CHANGE]
            self.remove (iter)

        mandatory = new_change.get_mandatory ()
        if mandatory == None:
            mandatory = default_mandatory

        if mandatory:
            lock_pixbuf = self.locked_pixbuf
        else:
            lock_pixbuf = self.unlocked_pixbuf

        discard_change = False
        if old_change:
            discard_change = new_change.merge_old_change (old_change)

        if not discard_change:
            row = self.prepend ()
            self.set (row,
                      self.COLUMN_CHANGE,      new_change,
                      self.COLUMN_IGNORE,      ignore,
                      self.COLUMN_MANDATORY,   mandatory,
                      self.COLUMN_LOCK_PIXBUF, lock_pixbuf,
                      self.COLUMN_DESCRIPTION, new_change.get_short_description ())
        self.emit ("changed", new_change)

    def clear (self):
        gtk.ListStore.clear (self)
        self.emit ("changed", None)

    def find (self, source, id):
        iter = self.get_iter_first ()
        while iter:
            next = self.iter_next (iter)
            change = self[iter][self.COLUMN_CHANGE]
            if change.get_source () == source and \
               change.get_id ()     == id:
                return iter
            iter = next
        return None


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
        self.lockdown_window = None

        self.last_save_time = 0

        self.window = gtk.Window ()
        self.window.set_title (_("Editing profile %s")%profile_name)
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


    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def __add_widget (self, ui_manager, widget):
        self.box.pack_start (widget, False, False, 0)

    def __setup_menus (self):
        actions = [
            ("ProfileMenu", None,            _("_Profile")),
            ("Save",        gtk.STOCK_SAVE,  _("_Save"),    "<control>S", _("Save profile"),             self.__handle_save),
            ("Quit",        gtk.STOCK_QUIT,  _("_Quit"),    "<control>Q", _("Close the current window"), self.__handle_quit),
            ("EditMenu",    None,            _("_Edit")),
            ("Changes",     gtk.STOCK_EDIT,  _("_Changes"), "<control>H", _("Edit changes"),             self.__handle_edit),
            ("Lockdown",    None,            _("_Lockdown"),"<control>L", _("Edit Lockdown settings"),   self.__handle_lockdown),
            ("HelpMenu",    None,            _("_Help")),
            ("Contents",    gtk.STOCK_ABOUT, _("_Contents"),None,         _("Help Contents"),            self.__handle_help),
            ("About",       gtk.STOCK_ABOUT, _("_About"),   None,         _("About Sabayon"),            self.__handle_about),
        ]
        toggle_actions = [
            ("EnforceMandatory", None, _("Enforce Mandatory"), None, _("Enforce mandatory settings in the editing session"), self.__handle_enforce_mandatory, True),
        ]
        action_group = gtk.ActionGroup ("WindowActions")
        action_group.add_actions (actions)
        action_group.add_toggle_actions (toggle_actions)

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

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def __changes_model_changed (self, model, change):
        self.__set_needs_saving (not model.get_iter_first () is None)

    def __do_save (self):
        # The changes model stores changes in reverse chronological order, so that
        # the latest changes are always visible at the top of the window.  To apply
        # the changes, we need them in chronological order.  So, we collect
        # all the changes and reverse that list before committing the changes.

        all_changes = []
        iter = self.changes_model.get_iter_first ()
        while iter:
            change    = self.changes_model[iter][ProfileChangesModel.COLUMN_CHANGE]
            ignore    = self.changes_model[iter][ProfileChangesModel.COLUMN_IGNORE]
            mandatory = self.changes_model[iter][ProfileChangesModel.COLUMN_MANDATORY]
            all_changes.append ((change, ignore, mandatory))
            iter = self.changes_model.iter_next (iter)

        all_changes.reverse ()

        # Commit the changes!

        for (change, ignore, mandatory) in all_changes:
            if not ignore:
                dprint ("Committing: %s, mandatory = %s", change.get_id (), mandatory)
                try:
                    change.get_source ().commit_change (change, mandatory)
                except:
                    errors.errors_log_recoverable_exception (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL,
                                                             "got an exception while commiting a change")

        # Done

        self.changes_model.clear ()
        self.profile.sync_changes ()

    def __do_saveconfirm (self):
        if self.last_save_time:
            dialog = saveconfirm.SaveConfirmationAlert (self.window,
                                                        self.profile_name,
                                                        time.time () - self.last_save_time)
            response = dialog.run ()
            dialog.destroy ()

            if response == gtk.RESPONSE_CANCEL or \
               response == gtk.RESPONSE_DELETE_EVENT:
                return False
            if response == gtk.RESPONSE_YES:
                self.__do_save ()

        return True

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_save (self, action):
        self.__do_save ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_quit (self, action):
        if self.__do_saveconfirm ():
            self.window.destroy ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_delete_event (self, window, event):
        return not self.__do_saveconfirm ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_help (self, action):
        try:
            gtk.show_uri (None, "ghelp:sabayon", gtk.get_current_event_time())
        except gobject.GError, e:
            pass

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_about (self, action):
        aboutdialog.show_about_dialog (self.window)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_edit (self, action):
        if not self.changes_window:
            self.changes_window = changeswindow.ChangesWindow (self.changes_model,
                                                               self.profile_name,
                                                               self.window)
            self.changes_window.window.connect ("delete-event",
                                                gtk.Widget.hide_on_delete)
        self.changes_window.window.present ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_lockdown (self, action):
        if not self.lockdown_window:
            debuglog.uprint ("Creating new Lockdown window")
            applier = LockdownApplierSabayon (self.profile, self.changes_model)
            self.lockdown_window = lockdowndialog.PessulusMainDialog (applier, False)
            self.lockdown_window.window.set_title (_("Lockdown settings for %s")%self.profile_name)
        else:
            debuglog.uprint ("Presenting existing Lockdown window")

        self.lockdown_window.window.present ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __handle_enforce_mandatory (self, action):
        active = action.get_active ()
        debuglog.uprint ("Setting enforce_mandatory to %s", active)
        self.profile.set_enforce_mandatory (active)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def __session_finished (self, session):
        self.window.destroy ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def __session_mapped (self, session_widget, event):
        dprint ("Session widget mapped; starting prototype session")
        self.session_widget.disconnect (self.mapped_handler_id)
        self.mapped_handler_id = 0
        self.session.connect ("finished", self.__session_finished)
        self.session.start (str (self.session_widget.session_window.xid))
        return False

    def __setup_session (self):
        self.session = protosession.ProtoSession (self.profile_name, self.display_number)

        try:
            self.session.apply_profile ()
        except errors.RecoverableApplyErrorException, e:
            errors_log_recoverable_exception (e)
            dialog = gtk.MessageDialog (parent = None,
                                        flags = gtk.DIALOG_MODAL,
                                        type = gtk.MESSAGE_ERROR,
                                        buttons = gtk.BUTTONS_NONE,
                                        message_format = _("There was a recoverable error while applying the "
                                                           "user profile '%s'.  You can report this error now "
                                                           "or try to continue editing the user profile."))
            (REPORT, CONTINUE) = range (2)
            dialog.add_button (_("_Report this error"), REPORT)
            dialog.add_button (_("_Continue editing"), CONTINUE)
            response = dialog.run ()
            dialog.destroy ()

            if response == REPORT:
                raise # the toplevel will catch the RecoverableApplyErrorException and exit

        except errors.FatalApplyErrorException, e:
            raise # FIXME: do we need any special processing?  Should we give the user
                  # the option of continuing editing?

        self.profile.start_monitoring ()
        screen = gtk.gdk.screen_get_default ()
        width  = (screen.get_width ()  * 3) / 4
        height = (screen.get_height () * 3) / 4

        dprint ("Creating %dx%d session widget", width, height)

        self.session_widget = sessionwidget.SessionWidget (width, height)
        self.box.pack_start (self.session_widget, True, True)
        self.mapped_handler_id = self.session_widget.connect ("map-event", self.__session_mapped)
        self.session_widget.show ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def __update_statusbar (self, model, change):
        if change:
            self.statusbar.pop (self.status_context_id)
            self.statusbar.push (self.status_context_id,
                                 change.get_short_description ())

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
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
