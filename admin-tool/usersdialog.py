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
import pwd
import gtk
import gtk.glade
import userdb
import errors
import debuglog

from config import *

class UsersModel (gtk.ListStore):
    (
        COLUMN_NAME,
        COLUMN_USER,
        COLUMN_APPLY
    ) = range (3)

    def __init__ (self, db, profile):
        gtk.ListStore.__init__ (self, str, str, bool)
        for user in db.get_users ():
            pw = pwd.getpwnam (user)

            name = None
            if pw.pw_gecos:
                name = pw.pw_gecos.split (",")[0]
            if not name:
                name = user

            row = self.append ()
            self.set (row,
                      self.COLUMN_NAME,  name,
                      self.COLUMN_USER,  user,
                      self.COLUMN_APPLY, profile == db.get_profile (user, False, True))

class UsersDialog:
    def __init__ (self, profile, parent):
        self.profile = profile
        self.userdb = userdb.get_database ()

        apply_to_all = self.userdb.get_default_profile (False) == profile
        
        glade_file = os.path.join (GLADEDIR, "sabayon.glade")
        self.xml = gtk.glade.XML (glade_file, "users_dialog", PACKAGE)

        self.dialog = self.xml.get_widget ("users_dialog")
        self.dialog.set_transient_for (parent)
        self.dialog.set_default_response (gtk.RESPONSE_CLOSE)
        self.dialog.set_icon_name ("sabayon")
        self.dialog.set_title (_("Users for profile %s")%profile)

        self.close_button = self.xml.get_widget ("users_close_button")

        self.help_button = self.xml.get_widget ("users_help_button")
        self.help_button.hide ()

        self.all_check = self.xml.get_widget ("users_all_check")
        self.all_check.set_active (apply_to_all)
        self.all_check.connect ("toggled", self.__all_check_toggled)

        self.users_model = UsersModel (self.userdb, self.profile)
        
        self.users_list_scroll = self.xml.get_widget ("users_list_scroll")
        self.users_list = self.xml.get_widget ("users_list")
        self.users_list.set_model (self.users_model)
        self.users_list.set_sensitive (not apply_to_all)

        c = gtk.TreeViewColumn (_("Name"),
                                gtk.CellRendererText (),
                                text = UsersModel.COLUMN_NAME)
        c.set_sort_column_id(UsersModel.COLUMN_NAME)        
        self.users_list.append_column (c)
        self.users_model.set_sort_column_id(UsersModel.COLUMN_NAME, gtk.SORT_ASCENDING)


        toggle = gtk.CellRendererToggle ()
        toggle.connect ("toggled", self.__on_use_toggled)
        c = gtk.TreeViewColumn (_("Use This Profile"))
        c.pack_start (toggle, False)
        c.set_attributes (toggle, active = UsersModel.COLUMN_APPLY)
        self.users_list.append_column (c)
        
        response = self.dialog.run ()
        self.dialog.hide ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __on_use_toggled (self, toggle, path):
        iter = self.users_model.get_iter_from_string (path)
        apply = self.users_model.get_value (iter, UsersModel.COLUMN_APPLY)

        apply = not apply

        self.users_model.set (iter, UsersModel.COLUMN_APPLY, apply)

        username = self.users_model.get_value (iter, UsersModel.COLUMN_USER)
        
        if apply:
            self.userdb.set_profile (username, self.profile)
        else:
            self.userdb.set_profile (username, None)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __all_check_toggled (self, toggle):
        apply_to_all = self.all_check.get_active ()
        self.users_list.set_sensitive (not apply_to_all)

        if apply_to_all:
            self.userdb.set_default_profile (self.profile)
        else:
            self.userdb.set_default_profile (None)

if __name__ == "__main__":
    import util

    util.init_gettext ()
    
    d = UsersDialog ("foo", None)
