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

class FilesChange (userprofile.ProfileChange):
    def __init__ (self, source, filename, event):
        userprofile.ProfileChange.__init__ (self, source)
        self.filename = filename
        self.event = event

    def get_name (self):
        return self.filename

    def get_type (self):
        return dirmonitor.event_to_string (self.event)

    def get_value (self):
        return ""

gobject.type_register (FilesChange)

def _safe_copy_file (file, srcdir, dstdir, force = False):
    """Copies @file in @srcdir to @dstdir, ensuring that all the
    parent directories of @file are created in @dstdir. @force
    specifies whether the copy should continue if existing
    files/directories are present.
    """
    #
    # FIXME: handle @force
    # FIXME: lots of error conditions being ignored here
    #
    dir = dstdir + "/" + os.path.dirname (file)
    if not os.access (dir, os.F_OK):
        os.makedirs (dir)
    shutil.copyfile (srcdir + "/" + file,
                     dstdir + "/" + file)
    
class FilesSource (userprofile.ProfileSource):
    def __init__ (self, profile_storage, source_name):
        userprofile.ProfileSource.__init__ (self, source_name)
        self.profile_storage = profile_storage
        self.home_dir = util.get_home_dir ()
        self.monitor = dirmonitor.DirectoryMonitor (self.home_dir,
                                                    self.__handle_monitor_event)

    def __handle_monitor_event (self, path, event):
        if os.path.isfile (path):
            self.emit_change (FilesChange (self, path, event))
	# TODO: register the file in the profile storage using 
	#       self.profile_storage.add_file()

    def commit_change (self, change, mandatory = False):
        #
        # FIXME: handle mandatory
        # FIXME: sanity check input (e.g. is change actually in homedir/?)
	# TODO: save change to the profile_storage using 
	#       self.profile_storage.update_all()
        #
        _safe_copy_file (change.get_name ()[len (self.home_dir):],
                         self.home_dir,
                         self.profile_storage.get_directory(),
                         True)
        
    def start_monitoring (self):
        self.monitor.start ()
        
    def stop_monitoring (self):
        self.monitor.stop ()
        
    def sync_changes (self):
        # Nothing to do here
        pass
    
    def apply (self):
        # FIXME: need to know the list of files and whether they are
        #        mandatory/defaults. The just use _safe_copy_file()
        #        to copy them over to self.profile_path
        pass

gobject.type_register (FilesSource)
    
def get_source (profile_storage):
    return FilesSource (profile_storage, "Files")

#
# Unit tests
#
def run_unit_tests ():
    import gobject
    import tempfile

    old_homedir = os.environ["HOME"]
    
    temp_path = tempfile.mkdtemp (dir = util.get_home_dir (),
                                  prefix = ".test-filesprofile-")
    os.environ["HOME"] = temp_path
    profile_path = tempfile.mkdtemp (prefix = "test-filesprofile-")

    def handle_change (source, change, data):
        (temp_path, main_loop) = data
        filename = change.get_name ()
        if len (filename) > len (temp_path) and \
           filename[:len (temp_path)] == temp_path:
            source.commit_change (change)
            main_loop.quit ()

    main_loop = gobject.MainLoop ()
    
    def should_not_be_reached ():
        assert False
        return True
    timeout = gobject.timeout_add (60 * 1000, should_not_be_reached)
    
    profile_storage = storage.ProfileStorage("FileTest.zip")
    try:
	profile_storage.install(profile_path)
    except:
        pass
    source = get_source (profile_storage)
    source.connect ("changed", handle_change, (temp_path, main_loop))
    source.start_monitoring ()

    os.makedirs (temp_path + "/foobar/foo/bar/foo/bar")
    
    f = file (temp_path + "/foobar/foo/bar/foo/bar" + "/foo", "w")
    f.close ()
    
    main_loop.run ()

    source.stop_monitoring ()

    assert os.access (profile_path + "/foobar/foo/bar/foo/bar" + "/foo", os.F_OK)

    shutil.rmtree (temp_path, True)
    shutil.rmtree (profile_path, True)

    gobject.source_remove (timeout)

    os.environ["HOME"] = old_homedir

