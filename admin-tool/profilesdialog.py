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

import os
import errno
import shutil
import tempfile
import pwd
import gobject
import gtk
import gtk.glade
import storage
import protosession
import util
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

def _get_profile_path_for_name (profile_name):
    return PROFILESDIR + "/" + profile_name + ".zip"

class ProfilesModel (gtk.ListStore):
    (
        COLUMN_NAME,
    ) = range (1)

    def __init__ (self):
        gtk.ListStore.__init__ (self, str)
        self.reload ()

    def reload (self):
        self.clear ()
        profile_files = []
        try:
            profile_files = os.listdir (PROFILESDIR)
        except OSError, err:
            if err.errno != errno.ENOENT:
                raise err
                                        
        for file in profile_files:
            if not file.endswith (".zip"):
                continue
                
            row = self.append ()
            self.set (row, self.COLUMN_NAME, file[:-len (".zip")])

class NewProfileDialog:
    def __init__ (self, profiles_model):
        self.profiles_model = profiles_model
        
        glade_file = GLADEDIR + '/' + "sabayon.glade"
        self.xml = gtk.glade.XML (glade_file, "new_profile_dialog")
        
        self.dialog = self.xml.get_widget ("new_profile_dialog")
        self.dialog.connect ("destroy", gtk.main_quit)
        self.dialog.set_default_response (gtk.RESPONSE_ACCEPT)

        self.create_button = self.xml.get_widget ("new_profile_create_button")
        self.create_button.set_sensitive (False)

        self.name_entry = self.xml.get_widget ("new_profile_name_entry")
        self.name_entry.connect ("changed", self.__name_entry_changed)
        self.name_entry.set_activates_default (True)
        
        self.base_combo = self.xml.get_widget ("new_profile_base_combo")
        self.base_combo.set_model (self.profiles_model)

        renderer = gtk.CellRendererText ()
        self.base_combo.pack_start (renderer, True)
        self.base_combo.set_attributes (renderer, text = ProfilesModel.COLUMN_NAME)

    def __name_entry_changed (self, entry):
        text = entry.get_text ()
        if not text or text.isspace ():
            self.create_button.set_sensitive (False)
        else:
            self.create_button.set_sensitive (True)

    def run (self, parent):
        self.name_entry.grab_focus ()
        self.dialog.set_transient_for (parent)
        self.dialog.present ()
        response = self.dialog.run ()
        self.dialog.hide ()
        
        if response != gtk.RESPONSE_ACCEPT:
            return None

        iter = self.base_combo.get_active_iter ()
        if iter:
            base = self.profiles_model.get_value (iter, ProfilesModel.COLUMN_NAME)
        else:
            base = None
        
        return (self.name_entry.get_text (), base)

class ProfilesDialog:
    def __init__ (self):
        assert os.geteuid () == 0
        
        glade_file = GLADEDIR + '/' + "sabayon.glade"
        self.xml = gtk.glade.XML (glade_file, "profiles_dialog")

        self.dialog = self.xml.get_widget ("profiles_dialog")
        self.dialog.connect ("destroy", gtk.main_quit)
        self.dialog.set_default_response (gtk.RESPONSE_ACCEPT)

        self.profiles_list = self.xml.get_widget ("profiles_list")
        self.__setup_profiles_list ()

        self.new_button = self.xml.get_widget ("new_button")
        self.__fix_button_align (self.new_button)
        self.new_button.connect ("clicked", self.__new_button_clicked)

        self.edit_button = self.xml.get_widget ("edit_button")
        self.__fix_button_align (self.edit_button)
        self.edit_button.connect ("clicked", self.__edit_button_clicked)
        
        self.delete_button = self.xml.get_widget ("delete_button")
        self.__fix_button_align (self.delete_button)
        self.delete_button.connect ("clicked", self.__delete_button_clicked)
        
        self.help_button = self.xml.get_widget ("help_button")
        self.help_button.set_sensitive (False)

        self.dialog.connect ("response", self.__dialog_response)

        (width, height) = self.profiles_list.size_request ()

        self.dialog.set_default_size (min (width + 250, 450),
                                      min (height + 190, 400))

        self.profiles_list.grab_focus ()
        self.__profile_selection_changed (self.profiles_list.get_selection ())

        self.dialog.show ()

    def __fix_button_align (self, button):
        child = button.get_child ()

        if isinstance (child, gtk.Alignment):
            child.set_property ("xalign", 0.0)
        elif isinstance (child, gtk.Label):
            child.set_property ("xalign", 0.0)

    def __setup_profiles_list (self):
        self.profiles_model = ProfilesModel ()
        self.profiles_list.set_model (self.profiles_model)

        self.profiles_list.get_selection ().set_mode (gtk.SELECTION_SINGLE)
        self.profiles_list.get_selection ().connect ("changed", self.__profile_selection_changed)

        c = gtk.TreeViewColumn ("Name",
                                gtk.CellRendererText (),
                                text = ProfilesModel.COLUMN_NAME)
        self.profiles_list.append_column (c)

    def __dialog_response (self, dialog, response_id):
        dialog.destroy ()

    def __new_button_clicked (self, button):
        (profile_name, base_profile) = NewProfileDialog (self.profiles_model).run (self.dialog)
        if profile_name:
            self.__create_new_profile (profile_name, base_profile)

    def __get_selected_profile (self):
        (model, row) = self.profiles_list.get_selection ().get_selected ()
        if not row:
            return None
        return model[row][ProfilesModel.COLUMN_NAME]

    def __copy_to_user (self, profile_path, username):
        (fd, user_path) = tempfile.mkstemp (prefix = "profile-%s-" % username, suffix = ".zip")
        os.close (fd)

        shutil.copyfile (profile_path, user_path)

        try:
            pw = pwd.getpwnam (username)
        except KeyError, e:
            errordialog = gtk.MessageDialog (None,
                                             gtk.DIALOG_DESTROY_WITH_PARENT,
                                             gtk.MESSAGE_ERROR,
                                             gtk.BUTTONS_CLOSE,
                                             "User account '%s' was not found" % username)
            errordialog.format_secondary_text ("Sabayon requires a special user account '%s' to be present on this computer. Try again after creating the account (using, for example, the 'adduser' command)" % (username))
                                               
            errordialog.run ()
            errordialog.destroy ()
            raise e
        
        os.chown (user_path, pw.pw_uid, pw.pw_gid)

        dprint ("Copied %s temporarily to %s" % (profile_path, user_path))

        return user_path

    def __copy_from_user (self, user_path, profile_path):
        os.chown (user_path, os.geteuid (), os.getegid ())
        os.rename (user_path, profile_path)
        dprint ("Moved %s back from %s" % (user_path, profile_path))

    def __edit_button_clicked (self, button):
        profile_name = self.__get_selected_profile ()
        if profile_name:
            # FIXME: shouldn't be hardcoded user name
	    # NOTE: created when installing the RPM package.
            username = "sabayon"
            profile_path = _get_profile_path_for_name (profile_name)

            user_path = self.__copy_to_user (profile_path, username)

            self.dialog.set_sensitive (False)
            
            argv = SESSION_TOOL_ARGV + [ "sabayon", user_path ]
            dprint ("Running session: %s" % argv)
            os.spawnv (os.P_WAIT, argv[0], argv)
            
            self.dialog.set_sensitive (True)

            self.__copy_from_user (user_path, profile_path)

    def __delete_button_clicked (self, button):
        profile_name = self.__get_selected_profile ()
        if profile_name:
            os.remove (_get_profile_path_for_name (profile_name))
            self.profiles_model.reload ()

    def __create_new_profile (self, profile_name, base_profile):
        profile_storage = storage.ProfileStorage (_get_profile_path_for_name (profile_name))
        profile_storage.update_all ("")

        self.profiles_model.reload ()
        iter = self.profiles_model.get_iter_first ()
        while iter:
            if self.profiles_model[iter][ProfilesModel.COLUMN_NAME] == profile_name:
                self.profiles_list.get_selection ().select_iter (iter)
                return
            iter = self.profiles_model.iter_next (iter)

    def __profile_selection_changed (self, selection):
        profile_name = self.__get_selected_profile ()
        self.edit_button.set_sensitive (profile_name != None)
        self.delete_button.set_sensitive (profile_name != None)
