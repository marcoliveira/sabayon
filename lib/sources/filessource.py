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
import os.path
import shutil
import util
import gobject
import userprofile
import dirmonitor
import storage
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_FILESSOURCE, fmt % args)

class FilesChange (userprofile.ProfileChange):
    def __init__ (self, source, rel_path, event):
        userprofile.ProfileChange.__init__ (self, source)
        self.rel_path = rel_path
        self.event    = event

        assert self.event == dirmonitor.CREATED or \
               self.event == dirmonitor.DELETED or \
               self.event == dirmonitor.CHANGED

    def get_id (self):
        return self.rel_path

    def get_short_description (self):
        if self.event == dirmonitor.CREATED:
            return "File '%s' created" % self.rel_path
        elif self.event == dirmonitor.DELETED:
            return "File '%s' deleted" % self.rel_path
        elif self.event == dirmonitor.CHANGED:
            return "File '%s' changed" % self.rel_path

gobject.type_register (FilesChange)

def _safe_copy_file (file, srcdir, dstdir, force = False):
    """Copies @file in @srcdir to @dstdir, ensuring that all the
    parent directories of @file are created in @dstdir. @force
    specifies whether the copy should continue if existing
    files/directories are present.
    """
    #
    # FIXME: lots of error conditions being ignored here
    #
    dir = dstdir + "/" + os.path.dirname (file)
    if not os.access (dir, os.F_OK):
        os.makedirs (dir)

    src = srcdir + "/" + file
    dst = dstdir + "/" + file

    if not os.path.exists (dst) or force:
        dprint ("Copying '%s' to '%s'" % (src, dst))
        shutil.copyfile (src, dst)
    
class FilesSource (userprofile.ProfileSource):
    def __init__ (self, profile_storage):
        userprofile.ProfileSource.__init__ (self, "Files")
        self.profile_storage = profile_storage
        self.home_dir = util.get_home_dir ()
        self.monitor = dirmonitor.DirectoryMonitor (self.home_dir,
                                                    self.__handle_monitor_event)
        self.monitor.set_directories_to_ignore (DIRECTORIES_TO_IGNORE)
        self.monitor.set_files_to_ignore (FILES_TO_IGNORE)

    def __handle_monitor_event (self, path, event):
        if os.path.isfile (path):
            # FIXME: sanity check input (e.g. is change actually in homedir/?)
            rel_path = path[len (self.home_dir):].lstrip ("/")
            dprint ("Emitting event '%s' on file '%s'" %
                    (dirmonitor.event_to_string (event), rel_path))
            self.emit_change (FilesChange (self, rel_path, event))

    def commit_change (self, change, mandatory = False):
        if userprofile.ProfileSource.commit_change (self, change, mandatory):
            return

        # FIXME: What about DELETED events ?

        dprint ("Commiting '%s' (mandatory = %s)" % (change.rel_path, mandatory))
                    
        _safe_copy_file (change.rel_path,
                         self.home_dir,
                         self.profile_storage.get_install_path (),
                         True)

        if mandatory:
            metadata = "mandatory"
        else:
            metadata = "default"

        self.profile_storage.add_file (change.rel_path, self.name, metadata)
        
    def start_monitoring (self):
        self.monitor.start ()
        
    def stop_monitoring (self):
        self.monitor.stop ()
        
    def sync_changes (self):
        # Nothing to do here
        pass
    
    def apply (self):
        for (file, handler, description) in self.profile_storage.info_all ():
            if handler != self.name:
                continue
            
            if description == "mandatory":
                mandatory = True
            else:
                mandatory = False
            
            _safe_copy_file (file,
                             self.profile_storage.get_install_path (),
                             self.home_dir,
                             mandatory)

gobject.type_register (FilesSource)
    
def get_source (profile_storage):
    return FilesSource (profile_storage)

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
    timeout = gobject.timeout_add (60 * 1000, should_not_be_reached)
    
    profile_storage = storage.ProfileStorage ("FileTest.zip")
    profile_storage.install ()
    source = get_source (profile_storage)
    source.connect ("changed", handle_change, main_loop)
    source.start_monitoring ()

    os.makedirs (temp_path + "/foobar/foo/bar/foo/bar")
    
    f = file (temp_path + "/foobar/foo/bar/foo/bar" + "/foo", "w")
    f.close ()
    
    main_loop.run ()

    source.stop_monitoring ()

    assert os.access (profile_storage.get_install_path () + "/foobar/foo/bar/foo/bar" + "/foo", os.F_OK)

    profile_storage.update_all ("")
    profile_storage.uninstall ()

    shutil.rmtree (temp_path, True)

    gobject.source_remove (timeout)

    temp_path = tempfile.mkdtemp (dir = real_homedir,
                                  prefix = ".test-filesprofile-")
    util.set_home_dir_for_unit_tests (temp_path)
    
    profile_storage = storage.ProfileStorage ("FileTest.zip")
    profile_storage.install ()

    assert os.access (profile_storage.get_install_path () + "/foobar/foo/bar/foo/bar" + "/foo", os.F_OK)
    
    source = get_source (profile_storage)
    source.apply ()
    
    assert os.access (temp_path + "/foobar/foo/bar/foo/bar" + "/foo", os.F_OK)
    
    shutil.rmtree (temp_path, True)

    profile_storage.uninstall ()

    os.remove ("FileTest.zip")
    if os.path.exists ("FileTest.zip.bak"):
        os.remove ("FileTest.zip.bak")
    
    util.set_home_dir_for_unit_tests (None)

