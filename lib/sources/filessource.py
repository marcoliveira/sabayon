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
import shutil
import gobject

try:
    import userprofile
    import dirmonitor
    import storage
    import util
    from config import *
    import debuglog
except:
    from sabayon import userprofile
    from sabayon import dirmonitor
    from sabayon import storage
    from sabayon import util
    from sabayon.config import *
    from sabayon import debuglog

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_FILES_SOURCE, fmt % args)

class FilesChange (userprofile.ProfileChange):
    def __init__ (self, source, rel_path, event):
        userprofile.ProfileChange.__init__ (self, source)
        self.rel_path = rel_path
        self.event    = event
        self.created = self.event == dirmonitor.CREATED

        assert self.event == dirmonitor.CREATED or \
               self.event == dirmonitor.DELETED or \
               self.event == dirmonitor.CHANGED

    def get_id (self):
        return self.rel_path

    def merge_old_change (self, old_change):
        self.created = old_change.created
        return self.event == dirmonitor.DELETED and self.created

    def get_ignore_default (self):
        # Ignore backup files by default
        if self.rel_path[-1] == "~":
            return True
        return False

    def get_short_description (self):
        utf8_rel_path = gobject.filename_display_name (self.rel_path)
        if os.path.isdir(self.rel_path):
            filetype = _("Directory")
        elif os.path.islink(self.rel_path):
            filetype = _("Link")
        else:
            filetype = _("File")
        if self.event == dirmonitor.CREATED:
            return _("%s '%s' created") % (filetype, utf8_rel_path)
        elif self.event == dirmonitor.DELETED:
            return _("%s '%s' deleted") % (filetype, utf8_rel_path)
        elif self.event == dirmonitor.CHANGED:
            return _("%s '%s' changed") % (filetype, utf8_rel_path)


gobject.type_register (FilesChange)

class FilesSource (userprofile.ProfileSource):
    def __init__ (self, storage):
        userprofile.ProfileSource.__init__ (self, _("Files"), "get_files_delegate")
        self.storage = storage
        self.home_dir = util.get_home_dir ()
        self.monitor = dirmonitor.DirectoryMonitor (self.home_dir,
                                                    self.__handle_monitor_event)
        self.monitor.set_directories_to_ignore (DIRECTORIES_TO_IGNORE)
        self.monitor.set_files_to_ignore (FILES_TO_IGNORE)
        self.SORTPRIORITY = 500

    def __handle_monitor_event (self, path, event):
        if event == dirmonitor.DELETED or os.path.isfile (path) or os.path.isdir (path):
            # FIXME: sanity check input (e.g. is change actually in homedir/?)
            rel_path = path[len (self.home_dir):].lstrip ("/")
            dprint ("Emitting event '%s' on file '%s'",
                    dirmonitor.event_to_string (event), rel_path)
            self.emit_change (FilesChange (self, rel_path, event))

    def get_path_description (self, path):
        if path == ".config/menus/applications.menu":
            return _("Applications menu")
        elif path == ".config/menus/settings.menu":
            return _("Settings menu")
        elif path == ".config/menus/server-settings.menu":
            return _("Server Settings menu")
        elif path == ".config/menus/system-settings.menu":
            return _("System Settings menu")
        elif path == ".config/menus/start-here.menu":
            return _("Start Here menu")
        else:
            return path

    def commit_change (self, change, mandatory = False):
        if userprofile.ProfileSource.commit_change (self, change, mandatory):
            return

        dprint ("Commiting '%s' (mandatory = %s)", change.rel_path, mandatory)
        
        if change.event == dirmonitor.CREATED or \
           change.event == dirmonitor.CHANGED:
            self.storage.add (change.rel_path,
                              self.home_dir,
                              self.name,
                              { "mandatory" : mandatory })
        elif change.event == dirmonitor.DELETED:
            try:
                self.storage.remove (change.rel_path)
            except:
                pass
        
    def start_monitoring (self):
        self.monitor.start ()
        
    def stop_monitoring (self):
        self.monitor.stop ()
        
    def sync_changes (self):
        # Nothing to do here
        pass

    def set_enforce_mandatory (self, enforce):
        # Nothing to do here
        pass

    def __apply_foreach (self, source, path):
        attributes = self.storage.get_attributes (path)
        mandatory = False
        if attributes.has_key ("mandatory"):
            if attributes["mandatory"].lower() == "true":
                mandatory = True

        self.storage.extract (path, self.home_dir, mandatory)
    
    def apply (self, is_sabayon_session):
        self.storage.foreach (self.__apply_foreach, source = self.name)

gobject.type_register (FilesSource)
    
def get_source (storage):
    return FilesSource (storage)

#
# Unit tests
#
def run_unit_tests ():
    import gobject
    import tempfile

    real_homedir = util.get_home_dir ()
    
    temp_path = tempfile.mkdtemp (dir = real_homedir,
                                  prefix = ".test-filesprofile-")
    util.set_home_dir_for_unit_tests (temp_path)

    def handle_change (source, change, main_loop):
        source.commit_change (change)
        main_loop.quit ()

    main_loop = gobject.MainLoop ()
    
    def should_not_be_reached ():
        assert False
        return True
    timeout = gobject.timeout_add_seconds (60, should_not_be_reached)

    profile_path = os.path.join (os.getcwd (), "file-test.zip")
    if os.path.exists (profile_path):
        os.remove (profile_path)
    
    store = storage.ProfileStorage (profile_path)
    source = get_source (store)
    source.connect ("changed", handle_change, main_loop)
    source.start_monitoring ()

    os.makedirs (os.path.join (temp_path, "foobar/foo/bar/foo/bar"))
    
    f = file (os.path.join (temp_path, "foobar/foo/bar/foo/bar", "foo"), "w")
    f.close ()
    
    main_loop.run ()

    source.stop_monitoring ()

    store.save ()
    assert os.path.exists (profile_path)

    shutil.rmtree (temp_path, True)

    gobject.source_remove (timeout)

    temp_path = tempfile.mkdtemp (dir = real_homedir,
                                  prefix = ".test-filesprofile-")
    util.set_home_dir_for_unit_tests (temp_path)
    
    source = get_source (storage.ProfileStorage (profile_path))
    source.apply (False)
    
    assert os.access (os.path.join (temp_path, "foobar/foo/bar/foo/bar/foo"), os.F_OK)
    
    shutil.rmtree (temp_path, True)

    os.remove (profile_path)
    
    util.set_home_dir_for_unit_tests (None)
