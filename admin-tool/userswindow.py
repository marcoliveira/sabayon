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
import util
import userdb

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)
    
class UsersModel (gtk.ListStore):
    (
        COLUMN_USER,
        COLUMN_PROFILE
    ) = range (2)

    def __init__ (self, userdb):
        gtk.ListStore.__init__ (self, str, str)

        self.userdb = userdb

        for username in self.userdb.get_users ():
            profile = self.userdb.get_profile (username)
            if not profile:
                profile = _("None")
            
            self.set (self.append (),
                      self.COLUMN_USER,    username,
                      self.COLUMN_PROFILE, profile)

class ProfilesModel (gtk.ListStore):
    (
        COLUMN_PROFILE,
        COLUMN_BITE_ME_GUIDO
    ) = range (2)

    def __init__ (self, userdb):
        gtk.ListStore.__init__ (self, str)

        self.userdb = userdb

        self.set (self.append (),
                  self.COLUMN_PROFILE, _("None"))
        for profile in self.userdb.get_profiles ():
            self.set (self.append (),
                      self.COLUMN_PROFILE, profile)

class UsersWindow (gtk.Window):
    def __init__ (self, parent_window = None):
        self.userdb = userdb.get_database ()
        
        gtk.Window.__init__ (self, gtk.WINDOW_TOPLEVEL)
        self.set_title (_("All Your Settings Are Belong To Us"))
        self.set_icon_name ("sabayon")
        self.set_transient_for (parent_window)
        self.set_destroy_with_parent (True)
        self.set_default_size (480, 380)

        self.main_vbox = gtk.VBox (False, 0)
        self.main_vbox.show ()
        self.add (self.main_vbox)

        self.scrolled = gtk.ScrolledWindow ()
        self.scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.set_shadow_type (gtk.SHADOW_IN)
        self.scrolled.show ()
        self.main_vbox.pack_start (self.scrolled, True, True, 0)

        self.__setup_treeview ()

    def __setup_treeview (self):
        self.users_model = UsersModel (self.userdb)
        self.profiles_model = ProfilesModel (self.userdb)

        self.treeview = gtk.TreeView (self.users_model)
        self.treeview.show ()
        self.scrolled.add (self.treeview)

        self.treeview.get_selection ().set_mode (gtk.SELECTION_SINGLE)
        self.treeview.set_headers_visible (True)

        c = gtk.TreeViewColumn (_("User"),
                                gtk.CellRendererText (),
                                text = UsersModel.COLUMN_USER)
        self.treeview.append_column (c)

        renderer = gtk.CellRendererCombo ()
        renderer.set_property ("text-column", ProfilesModel.COLUMN_PROFILE)
        renderer.set_property ("editable", True)
        renderer.set_property ("has-entry", False)
        renderer.set_property ("model", self.profiles_model)
        renderer.connect ("edited", self.__profile_changed)

        c = gtk.TreeViewColumn (_("Profile"),
                                renderer,
                                text = UsersModel.COLUMN_PROFILE)
        self.treeview.append_column (c)

    def __profile_changed (self, cell, tree_path, profile):
        iter = self.users_model.get_iter_from_string (tree_path)
        username = self.users_model[iter][UsersModel.COLUMN_USER]

        dprint ("Setting profile for '%s' to '%s'", username, profile)
        
        if profile == _("None"):
            self.users_model[iter][UsersModel.COLUMN_PROFILE] = None
        else:
            self.users_model[iter][UsersModel.COLUMN_PROFILE] = profile
        
        self.userdb.set_profile (username, profile)

if __name__ == "__main__":
    util.init_gettext ()

    window = UsersWindow ()
    window.connect ("destroy", gtk.main_quit)
    window.show ()

    gtk.main ()
