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
        COLUMN_IGNORE,
        COLUMN_MANDATORY,
        COLUMN_DESCRIPTION
    ) = range (4)

    def __init__ (self, profile):
        gtk.ListStore.__init__ (self, userprofile.ProfileChange, bool, bool, str, str)

        self.profile = profile
        self.profile.connect ("changed", self.handle_profile_change)
        self.profile.start_monitoring ()

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

        row = self.prepend ()
        self.set (row,
                  self.COLUMN_CHANGE,      new_change,
                  self.COLUMN_IGNORE,      ignore,
                  self.COLUMN_MANDATORY,   mandatory,
                  self.COLUMN_DESCRIPTION, new_change.get_short_description ())

class ProfileMonitorWindow:
    #
    # profile_file is the path to the current profile to load/save
    #              it may not exist
    #
    def __init__ (self, profile_file):
        self.profile_file = profile_file
        self.profile = userprofile.UserProfile (profile_file)
        
        glade_file = os.path.join (GLADEDIR, "sabayon.glade")
        self.xml = gtk.glade.XML (glade_file, "monitor_window")

        self.window = self.xml.get_widget ("monitor_window")
        self.window.connect ("destroy", gtk.main_quit)
        self.window.set_icon_name ("sabayon")
        
        self.treeview = self.xml.get_widget ("changes_treeview")
        self.__setup_treeview ()

        self.save_item = self.xml.get_widget ("save_item")
        self.save_item.connect ("activate", self.__handle_save)
        
        self.quit_item = self.xml.get_widget ("quit_item")
        self.quit_item.connect ("activate", self.__handle_quit)

        self.about_item = self.xml.get_widget ("about_item")
        self.about_item.connect ("activate", self.__handle_about)

        self.window.show ()
        
        self.about = None

    def __handle_save (self, item):
        iter = self.changes_model.get_iter_first ()
        while iter:
            change    = self.changes_model[iter][ProfileChangesModel.COLUMN_CHANGE]
            ignore    = self.changes_model[iter][ProfileChangesModel.COLUMN_IGNORE]
            mandatory = self.changes_model[iter][ProfileChangesModel.COLUMN_MANDATORY]

            if not ignore:
                dprint ("Committing: %s, mandatory = %s" % (change.get_id (), mandatory))
                change.get_source ().commit_change (change, mandatory)
                
            iter = self.changes_model.iter_next (iter)
        
        self.changes_model.clear ()
        self.profile.sync_changes ()
    
    def __handle_quit (self, item):
        self.window.destroy ()

    def __handle_about (self, item):
        #
        # Of course, this would all be so much easier if
        # gtk_show_about_dialog() was wrapped
        #
        if self.about:
            self.about.show ()
            return

        authors = [
            "Daniel Veillard <veillard@redhat.com>",
            "John Dennis <jdennis@redhat.com>",
            "Mark McLoughlin <markmc@redhat.com>"
        ]

        # documenters = [
        # ]

        self.about = gtk.AboutDialog ()
        
        self.about.set_transient_for (self.window)
        self.about.set_destroy_with_parent (True)
        self.about.set_icon_name ("sabayon")

        self.about.set_name               ("Sabayon")
        self.about.set_version            (VERSION)
        self.about.set_copyright          ("(C) 2005 Red Hat, Inc.")
        self.about.set_website            ("http://www.gnome.org/projects/sabayon")
        self.about.set_comments           (_("Program to establish and edit profiles for users"))
        self.about.set_authors            (authors)
        self.about.set_logo_icon_name     ("sabayon")
        self.about.set_translator_credits (_("translator-credits"))

        # self.about.set_documenters        (documenters)

        def handle_delete (about, event):
            about.hide ()
            return True
        self.about.connect ("delete-event", handle_delete)

        def handle_response (about, response):
            about.hide ()
        self.about.connect ("response", handle_response)

        self.about.show ()

    def __on_ignore_toggled (self, toggle, path):
        iter = self.changes_model.get_iter_from_string (path)
        ignore = self.changes_model.get_value (iter, ProfileChangesModel.COLUMN_IGNORE)
        
        ignore = not ignore

        self.changes_model.set (iter, ProfileChangesModel.COLUMN_IGNORE, ignore)
    
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
        toggle.connect ("toggled", self.__on_ignore_toggled)
        c = gtk.TreeViewColumn (_("Ignore"),
                                toggle,
                                active = ProfileChangesModel.COLUMN_IGNORE)
        self.treeview.append_column (c)
                                
        toggle = gtk.CellRendererToggle ()
        toggle.connect ("toggled", self.__on_mandatory_toggled)
        c = gtk.TreeViewColumn (_("Mandatory"),
                                toggle,
                                active = ProfileChangesModel.COLUMN_MANDATORY)
        self.treeview.append_column (c)
        
        c = gtk.TreeViewColumn (_("Description"),
                                gtk.CellRendererText (),
                                text = ProfileChangesModel.COLUMN_DESCRIPTION)
        self.treeview.append_column (c)

    def __treeview_selection_changed (self, selection):
        (model, row) = selection.get_selected ()
        if row:
            change = model[row][ProfileChangesModel.COLUMN_CHANGE]
            dprint ("Selected: %s" % model[row][ProfileChangesModel.COLUMN_CHANGE].get_id ())
