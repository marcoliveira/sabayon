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
import userprofile
import util
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class ProfileChangesModel (gtk.ListStore):
    (
        COLUMN_CHANGE,
        COLUMN_MANDATORY,
        COLUMN_SOURCE,
        COLUMN_NAME,
        COLUMN_TYPE,
        COLUMN_VALUE
    ) = range (6)

    def __init__ (self, profile):
        gtk.ListStore.__init__ (self, userprofile.ProfileChange, bool, str, str, str, str)

        self.profile = profile
        self.profile.connect ("changed", self.handle_profile_change)
        self.profile.start_monitoring ()

    def handle_profile_change (self, profile, change):
        mandatory = False
        iter = self.get_iter_first ()
        while iter:
            next = self.iter_next (iter)
            if self[iter][self.COLUMN_SOURCE] == change.get_source_name () and \
               self[iter][self.COLUMN_NAME] == change.get_name ():
                mandatory = self[iter][self.COLUMN_MANDATORY]
                self.remove (iter)
            iter = next

        row = self.prepend ()
        self.set (row,
                  self.COLUMN_CHANGE, change,
                  self.COLUMN_MANDATORY, mandatory,
                  self.COLUMN_SOURCE, change.get_source_name (),
                  self.COLUMN_NAME, change.get_name (),
                  self.COLUMN_TYPE, change.get_type (),
                  self.COLUMN_VALUE, change.get_value ())

class ProfileMonitorWindow:
    #
    # profile_file is the path to the current profile to load/save
    #              it may not exist
    #
    def __init__ (self, profile_file):
        self.profile_file = profile_file
        self.profile = userprofile.UserProfile (profile_file)
        
        glade_file = GLADEDIR + '/' + "sabayon.glade"
        self.xml = gtk.glade.XML (glade_file, "monitor_window")

        self.window = self.xml.get_widget ("monitor_window")
        self.window.connect ("destroy", gtk.main_quit)
        
        self.treeview = self.xml.get_widget ("changes_treeview")
        self.__setup_treeview ()

        self.commit_item = self.xml.get_widget ("commit_item")
        self.commit_item.connect ("activate", self.__handle_commit)
        
        self.save_item = self.xml.get_widget ("save_item")
        self.save_item.connect ("activate", self.__handle_save)
        
        self.quit_item = self.xml.get_widget ("quit_item")
        self.quit_item.connect ("activate", self.__handle_quit)

        self.window.show ()

    def __handle_commit (self, item):
        (model, row) = self.treeview.get_selection ().get_selected ()
        if row:
            change = model[row][ProfileChangesModel.COLUMN_CHANGE]
            mandatory = model[row][ProfileChangesModel.COLUMN_MANDATORY]
            dprint ("Committing: %s, mandatory = %s" % (change.get_name (), mandatory))
            change.get_source ().commit_change (change, mandatory)
    
    def __handle_save (self, item):
        self.profile.sync_changes ()
    
    def __handle_quit (self, item):
        self.window.destroy ()

    def __on_mandatory_toggled (self, toggle, path):
        iter = self.changes_model.get_iter_from_string (path)
        mandatory = self.changes_model.get_value (iter, ProfileChangesModel.COLUMN_MANDATORY)
        
        mandatory = not mandatory

        self.changes_model.set (iter, ProfileChangesModel.COLUMN_MANDATORY, mandatory)
    
    def __setup_treeview (self):
        self.changes_model = ProfileChangesModel (self.profile)
        self.treeview.set_model (self.changes_model)
        
        self.treeview.get_selection ().set_mode (gtk.SELECTION_SINGLE)
        self.treeview.get_selection ().connect ("changed", self.__treeview_selection_changed)

        toggle = gtk.CellRendererToggle ()
        toggle.connect ("toggled", self.__on_mandatory_toggled)
        
        c = gtk.TreeViewColumn ("Mandatory",
                                toggle,
                                active = ProfileChangesModel.COLUMN_MANDATORY)
        self.treeview.append_column (c)
                                
        c = gtk.TreeViewColumn ("Source",
                                gtk.CellRendererText (),
                                text = ProfileChangesModel.COLUMN_SOURCE)
        self.treeview.append_column (c)
        
        c = gtk.TreeViewColumn ("Name",
                                gtk.CellRendererText (),
                                text = ProfileChangesModel.COLUMN_NAME)
        self.treeview.append_column (c)
        
        c = gtk.TreeViewColumn ("Type",
                                gtk.CellRendererText (),
                                text = ProfileChangesModel.COLUMN_TYPE)
        self.treeview.append_column (c)
        
        c = gtk.TreeViewColumn ("Value",
                                gtk.CellRendererText (),
                                text = ProfileChangesModel.COLUMN_VALUE)
        self.treeview.append_column (c)

    def __treeview_selection_changed (self, selection):
        (model, row) = selection.get_selected ()
        if row:
            change = model[row][ProfileChangesModel.COLUMN_CHANGE]
            dprint ("Selected: %s" % model[row][ProfileChangesModel.COLUMN_CHANGE].get_name ())
