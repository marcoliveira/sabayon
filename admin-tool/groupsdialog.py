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
import systemdb
import errors
import debuglog

from config import *

class GroupsModel (gtk.ListStore):
    (
        COLUMN_GROUP,
        COLUMN_APPLY
    ) = range (2)

    def __init__ (self, db, profile):
        gtk.ListStore.__init__ (self, str, bool)
        for group in db.get_groups ():

            row = self.append ()
            self.set (row,
                      self.COLUMN_GROUP, group,
                      self.COLUMN_APPLY, profile == db.get_profile (group,
                          False, True))

class GroupsDialog:
    def __init__ (self, profile, parent):
        self.profile = profile
        self.groupdb = systemdb.get_group_database ()

        glade_file = os.path.join (GLADEDIR, "sabayon.glade")
        self.xml = gtk.glade.XML (glade_file, "groups_dialog", PACKAGE)

        self.dialog = self.xml.get_widget ("groups_dialog")
        self.dialog.set_transient_for (parent)
        self.dialog.set_default_response (gtk.RESPONSE_CLOSE)
        self.dialog.set_icon_name ("sabayon")
        self.dialog.set_title (_("Groups for profile %s")%profile)

        self.close_button = self.xml.get_widget ("groups_close_button")

        self.help_button = self.xml.get_widget ("groups_help_button")
        self.help_button.hide ()

        self.groups_model = GroupsModel (self.groupdb, self.profile)
        
        self.groups_list_scroll = self.xml.get_widget ("groups_list_scroll")
        self.groups_list = self.xml.get_widget ("groups_list")
        self.groups_list.set_model (self.groups_model)

        c = gtk.TreeViewColumn (_("Group"),
                                gtk.CellRendererText (),
                                text = GroupsModel.COLUMN_GROUP)
        c.set_sort_column_id(GroupsModel.COLUMN_GROUP)
        self.groups_list.append_column (c)
        self.groups_model.set_sort_column_id(GroupsModel.COLUMN_GROUP, gtk.SORT_ASCENDING)


        toggle = gtk.CellRendererToggle ()
        toggle.connect ("toggled", self.__on_use_toggled)
        c = gtk.TreeViewColumn (_("Use This Profile"))
        c.pack_start (toggle, False)
        c.set_attributes (toggle, active = GroupsModel.COLUMN_APPLY)
        self.groups_list.append_column (c)
        
        response = self.dialog.run ()
        self.dialog.hide ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __on_use_toggled (self, toggle, path):
        iter = self.groups_model.get_iter_from_string (path)
        apply = self.groups_model.get_value (iter, GroupsModel.COLUMN_APPLY)

        apply = not apply

        self.groups_model.set (iter, GroupsModel.COLUMN_APPLY, apply)

        groupname = self.groups_model.get_value (iter, GroupsModel.COLUMN_GROUP)
        
        if apply:
            self.groupdb.set_profile (groupname, self.profile)
        else:
            self.groupdb.set_profile (groupname, None)

if __name__ == "__main__":
    import util

    util.init_gettext ()
    
    d = GroupsDialog ("foo", None)
