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
import os.path
import sys
import shutil
import tempfile
import pwd
import gobject
import gtk
import gtk.glade
import storage
import editorwindow
import usersdialog
import util
import userdb
import protosession
import debuglog
import errors
from config import *

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL, fmt % args)

def mprint (fmt, *args):
    debuglog.debug_log (True, debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL, fmt % args)

def _get_profile_path_for_name (profile_name):
    return os.path.join (PROFILESDIR, profile_name + ".zip")

class Session (gobject.GObject):
    __gsignals__ = {
        "finished" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }

    def __init__ (self, username, profile_name):
        gobject.GObject.__init__ (self)

        self.username     = username
        self.profile_name = profile_name
        self.profile_path = _get_profile_path_for_name (profile_name)

        self.pw = pwd.getpwnam (self.username)

        self.user_profile_path = None
        self.temp_homedir      = None

        self.session_pid             = 0
        self.session_child_watch     = 0
        self.session_stderr          = None
        self.session_stderr_watch_id = 0
        self.session_log_str         = ""

    def __del__ (self):
        if self.temp_homedir:
            protosession.reset_shell_and_homedir (self.username, self.temp_homedir)
            self.temp_homedir = None
        if self.user_profile_path:
            os.remove (self.user_profile_path)
            self.user_profile_path = None
        if self.temp_xauth_path:
            os.remove (self.temp_xauth_path)
            self.temp_xauth_path = None

    def __copy_xauthority (self):
        if not os.environ.has_key ("XAUTHORITY"):
            return None

        xauthority = os.environ["XAUTHORITY"]

        (fd, temp_path) = tempfile.mkstemp (prefix = "xauth-%s-" % self.username)
        os.close (fd)

        shutil.copy2 (xauthority, temp_path)

        os.chown (temp_path, self.pw.pw_uid, self.pw.pw_gid)

        dprint ("Copied $XAUTHORITY (%s) temporarily to %s", xauthority, temp_path)

        return temp_path

    def __copy_to_user (self, profile_path):
        (fd, user_path) = tempfile.mkstemp (prefix = "profile-%s-" % self.username, suffix = ".zip")
        os.close (fd)

        shutil.copy2 (profile_path, user_path)

        os.chown (user_path, self.pw.pw_uid, self.pw.pw_gid)

        dprint ("Copied %s temporarily to %s", profile_path, user_path)

        return user_path

    def __copy_from_user (self, user_path, profile_path):
        os.chown (user_path, os.geteuid (), os.getegid ())
        shutil.move (user_path, profile_path)
        dprint ("Moved %s back from %s", user_path, profile_path)

    @errors.checked_callback
    def __session_child_watch_handler (self, pid, status):
        if not os.WIFEXITED (status):
            exit_code = util.EXIT_CODE_FATAL

            if os.WIFSIGNALED (status):
                signal_num = os.WTERMSIG (status)

                mprint ("sabayon-session exited with SIGNAL %s", signal_num)
            else:
                mprint ("sabayon-session exited for an unknown reason")
        else:
            exit_code = os.WEXITSTATUS (status)

            # Here we cannot throw an exception for the error cases,
            # since we are a callback running out of the Glib main
            # loop.  So we have to set a flag and let the code
            # *outside* the main loop pick it up.

            if exit_code == util.EXIT_CODE_NORMAL:
                mprint ("sabayon-session exited normally")
                success = True
            elif exit_code == util.EXIT_CODE_RECOVERABLE:
                errors.errors_log_recoverable_error (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL,
                                                     "sabayon-session exited with RECOVERABLE exit status")
                # FIXME: throw a warning dialog
            else:
                errors.errors_log_fatal_error (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL,
                                               "sabayon-session exited with a FATAL ERROR (exit code %s)" % exit_code)
                gtk.main_quit () # so that the toplevel 'sabayon' will exit the main loop and show the fatal error

        protosession.clobber_user_processes (self.username)
        protosession.reset_shell_and_homedir (self.username, self.temp_homedir)
        self.temp_homedir = None

        if self.temp_xauth_path:
            os.remove (self.temp_xauth_path)
            self.temp_xauth_path = None

        self.__copy_from_user (self.user_profile_path, self.profile_path)
        self.user_profile_path = None

        self.session_pid         = 0
        self.session_child_watch = 0

        gobject.source_remove (self.session_stderr_watch_id)
        self.session_stderr_watch_id = 0

        self.session_stderr.close ()
        self.session_stderr = None

        self.emit ("finished")

        return False

    def build_envp_for_child (self):
        # gobject.spawn_async() wants a sequence, not a dictionary, so we build a sequence...
        new_environ = []
        for key in PASSTHROUGH_ENVIRONMENT:
            if os.environ.has_key (key):
                new_environ.append ("%s=%s" % (key, os.environ[key]))

        new_environ = new_environ + ["PATH=%s"     % DEFAULT_PATH,
                                     "SHELL=%s"    % DEFAULT_SHELL,
                                     "DISPLAY=%s"  % os.environ["DISPLAY"],
                                     "HOME=%s"     % self.temp_homedir,
                                     "LOGNAME=%s"  % self.pw.pw_name,
                                     "USER=%s"     % self.pw.pw_name,
                                     "USERNAME=%s" % self.pw.pw_name]

        if self.temp_xauth_path:
            new_environ.append ("XAUTHORITY=%s" % self.temp_xauth_path)

        return new_environ

    @errors.checked_callback
    def session_stderr_io_cb (self, source_fd, condition, session):
        if condition & gobject.IO_IN:
            s = session.session_stderr.read ()
            session.session_log_str = session.session_log_str + s
#            print "%s: got from sabayon-session stderr: \n<BEGIN SABAYON-SESSION STDERR>\n%s\n<END SABAYON-SESSION STDERR>" % (os.getpid (), s)

        if condition & gobject.IO_HUP:
            mprint ("========== BEGIN SABAYON-SESSION LOG ==========\n"
                    "%s\n"
                    "========== END SABAYON-SESSION LOG ==========",
                    session.session_log_str)
            return False

        return True

    def start (self):
        self.user_profile_path = self.__copy_to_user (self.profile_path)
        self.temp_homedir = protosession.setup_shell_and_homedir (self.username)
        protosession.clobber_user_processes (self.username)

        display_number = protosession.find_free_display ()

        self.temp_xauth_path = self.__copy_xauthority ()

        def child_setup_fn (self):
            os.setgid (self.pw.pw_gid)
            os.setuid (self.pw.pw_uid)
            os.setsid ()
            os.umask (022)

        # FIXME: get_readable_log_config_filename() doesn't work here.
        # Create a temporary copy of the log config file and use *that*.
        argv = SESSION_TOOL_ARGV + [ ("--admin-log-config=%s" % util.get_admin_log_config_filename ()),
                                     ("--readable-log-config=%s" % util.get_readable_log_config_filename ()),
                                     self.profile_name,
                                     self.user_profile_path,
                                     str (display_number) ]
        envp = self.build_envp_for_child ()
        cwd = self.temp_homedir

        # FIXME: do we need any special processing if this throws an exception?
        # We'll catch it in the toplevel and exit with a fatal error code, anyway.
        (pid, oink, oink, stderr_fd) = gobject.spawn_async (argv, envp, cwd,
                                                            gobject.SPAWN_DO_NOT_REAP_CHILD,
                                                            child_setup_fn, self,
                                                            None, None, True)	# stdin, stdout, stderr

        self.session_pid = pid;
        self.session_stderr = os.fdopen (stderr_fd)
        self.session_stderr_watch_id = gobject.io_add_watch (stderr_fd,
                                                             gobject.IO_IN | gobject.IO_HUP,
                                                             self.session_stderr_io_cb, self)
        self.session_child_watch = gobject.child_watch_add (self.session_pid,
                                                            self.__session_child_watch_handler)

gobject.type_register (Session)

class ProfilesModel (gtk.ListStore):
    (
        COLUMN_NAME,
    ) = range (1)

    def __init__ (self):
        gtk.ListStore.__init__ (self, str)
        self.reload ()

    def reload (self):
        self.clear ()
        profiles = userdb.get_database ().get_profiles ()
        profiles.sort ()
        for profile in profiles:
            self.set (self.append (),
                      self.COLUMN_NAME, profile)

class AddProfileDialog:
    def __init__ (self, profiles_model):
        self.profiles_model = profiles_model

        glade_file = os.path.join (GLADEDIR, "sabayon.glade")
        self.xml = gtk.glade.XML (glade_file, "add_profile_dialog")

        self.dialog = self.xml.get_widget ("add_profile_dialog")
        self.dialog.connect ("destroy", gtk.main_quit)
        self.dialog.set_default_response (gtk.RESPONSE_ACCEPT)
        self.dialog.set_icon_name ("sabayon")

        self.add_button = self.xml.get_widget ("add_profile_add_button")
        self.add_button.set_sensitive (False)

        self.name_entry = self.xml.get_widget ("add_profile_name_entry")
        self.name_entry.connect ("changed", self.__name_entry_changed)
        self.name_entry.set_activates_default (True)

        self.base_combo = self.xml.get_widget ("add_profile_base_combo")
        self.base_combo.set_model (self.profiles_model)
        if self.profiles_model.get_iter_first () is None:
            self.base_combo.set_sensitive (False)

        renderer = gtk.CellRendererText ()
        self.base_combo.pack_start (renderer, True)
        self.base_combo.set_attributes (renderer, text = ProfilesModel.COLUMN_NAME)

    @errors.checked_callback
    def __name_entry_changed (self, entry):
        text = entry.get_text ()
        if not text or text.isspace ():
            self.add_button.set_sensitive (False)
        else:
            self.add_button.set_sensitive (True)

    def run (self, parent):
        self.name_entry.grab_focus ()
        self.dialog.set_transient_for (parent)
        self.dialog.present ()
        response = self.dialog.run ()
        self.dialog.hide ()

        if response != gtk.RESPONSE_ACCEPT:
            return (None, None)

        row = self.base_combo.get_active_iter ()
        if row:
            base = self.profiles_model.get_value (row, ProfilesModel.COLUMN_NAME)
        else:
            base = None

        return (self.name_entry.get_text (), base)

class ProfilesDialog:
    def __init__ (self):
        assert os.geteuid () == 0

        glade_file = os.path.join (GLADEDIR, "sabayon.glade")
        self.xml = gtk.glade.XML (glade_file, "profiles_dialog")

        self.dialog = self.xml.get_widget ("profiles_dialog")
        self.dialog.connect ("destroy", gtk.main_quit)
        self.dialog.set_default_response (gtk.RESPONSE_ACCEPT)
        self.dialog.set_icon_name ("sabayon")

        self.profiles_list = self.xml.get_widget ("profiles_list")
        self.__setup_profiles_list ()

        self.profiles_list.connect ("key-press-event", self.__handle_key_press)

        self.add_button = self.xml.get_widget ("add_button")
        self.add_button.connect ("clicked", self.__add_button_clicked)

        self.remove_button = self.xml.get_widget ("remove_button")
        self.remove_button.connect ("clicked", self.__remove_button_clicked)

        self.edit_button = self.xml.get_widget ("edit_button")
        self.__fix_button_align (self.edit_button)
        self.edit_button.connect ("clicked", self.__edit_button_clicked)

        self.details_button = self.xml.get_widget ("details_button")
        self.__fix_button_align (self.details_button)
        self.details_button.connect ("clicked", self.__details_button_clicked)

        self.users_button = self.xml.get_widget ("users_button")
        self.__fix_button_align (self.users_button)
        self.users_button.connect ("clicked", self.__users_button_clicked)

        self.help_button = self.xml.get_widget ("help_button")
        self.help_button.hide ()

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

        c = gtk.TreeViewColumn (_("Name"),
                                gtk.CellRendererText (),
                                text = ProfilesModel.COLUMN_NAME)
        self.profiles_list.append_column (c)

    @errors.checked_callback
    def __dialog_response (self, dialog, response_id):
        dialog.destroy ()

    @errors.checked_callback
    def __add_button_clicked (self, button):
        (profile_name, base_profile) = AddProfileDialog (self.profiles_model).run (self.dialog)
        if profile_name:
            self.__create_new_profile (profile_name, base_profile)

    def __get_selected_profile (self):
        (model, row) = self.profiles_list.get_selection ().get_selected ()
        if not row:
            return None
        return model[row][ProfilesModel.COLUMN_NAME]

    @errors.checked_callback
    def __session_finished (self, session):
        debuglog.uprint ("Finishing editing profile")
        self.dialog.set_sensitive (True)

    @errors.checked_callback
    def __edit_button_clicked (self, button):
        profile_name = self.__get_selected_profile ()
        if profile_name:
            self.dialog.set_sensitive (False)

            session = Session (PROTOTYPE_USER, profile_name)
            session.connect ("finished", self.__session_finished)
            debuglog.uprint ("Starting to edit profile '%s'", profile_name)
            session.start ()

    @errors.checked_callback
    def __details_button_clicked (self, button):
        profile_name = self.__get_selected_profile ()
        if profile_name:
            editorwindow.ProfileEditorWindow (profile_name, self.dialog)

    @errors.checked_callback
    def __users_button_clicked (self, button):
        profile_name = self.__get_selected_profile ()
        if profile_name:
            usersdialog.UsersDialog (profile_name, self.dialog)

    def __delete_currently_selected (self):
        (model, selected) = self.profiles_list.get_selection ().get_selected ()
        if selected:
            if model.iter_next (selected):
                select = model[model.iter_next (selected)][ProfilesModel.COLUMN_NAME]
            else:
                select = None
                row = model.get_iter_first ()
                while row and model.iter_next (row):
                    next = model.iter_next (row)
                    if model.get_string_from_iter (next) == model.get_string_from_iter (selected):
                        select = model[row][ProfilesModel.COLUMN_NAME]
                        break
                    row = next

            profile_name = model[selected][ProfilesModel.COLUMN_NAME]
            dprint ("Deleting '%s'", profile_name)
            os.remove (_get_profile_path_for_name (profile_name))

            db = userdb.get_database ()
            if db.get_default_profile (False) == profile_name:
                db.set_default_profile (None)
            for user in db.get_users ():
                if db.get_profile (user, False, True) == profile_name:
                    db.set_profile (user, None)

            self.profiles_model.reload ()

            row = None
            if select:
                row = self.profiles_model.get_iter_first ()
                while row:
                    if select == model[row][ProfilesModel.COLUMN_NAME]:
                        break
                    row = model.iter_next (row)
            if not row:
                row = self.profiles_model.get_iter_first ()
            if row:
                self.profiles_list.get_selection ().select_iter (row)

    @errors.checked_callback
    def __remove_button_clicked (self, button):
        self.__delete_currently_selected ()

    @errors.checked_callback
    def __handle_key_press (self, profiles_list, event):
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete):
            self.__delete_currently_selected ()

    def __make_unique_profile_name (self, profile_name):
        profiles = userdb.get_database ().get_profiles ()

        name = profile_name
        idx = 1
        while name in profiles:
            #
            # Translators: this string specifies how a profile
            #              name is concatenated with an integer
            #              to form a unique profile name e.g.
            #              "Artist Workstation (5)"
            #
            name = _("%s (%s)") % (profile_name, idx)
            idx += 1

        return name

    def __create_new_profile (self, profile_name, base_profile):
        profile_name = self.__make_unique_profile_name (profile_name)

        if base_profile:
            base_storage = storage.ProfileStorage (base_profile)
            new_storage = base_storage.copy (profile_name)
        else:
            new_storage = storage.ProfileStorage (profile_name)
            new_storage.save ()

        self.profiles_model.reload ()
        row = self.profiles_model.get_iter_first ()
        while row:
            if self.profiles_model[row][ProfilesModel.COLUMN_NAME] == profile_name:
                self.profiles_list.get_selection ().select_iter (row)
                return
            row = self.profiles_model.iter_next (row)

    @errors.checked_callback
    def __profile_selection_changed (self, selection):
        profile_name = self.__get_selected_profile ()
        self.edit_button.set_sensitive (profile_name != None)
        self.details_button.set_sensitive (profile_name != None)
        self.users_button.set_sensitive (profile_name != None)
        self.remove_button.set_sensitive (profile_name != None)
