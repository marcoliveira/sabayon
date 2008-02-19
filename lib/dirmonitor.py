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
import gobject
import gnomevfs
import util
import fnmatch
import debuglog
import urllib

N_WATCHES_LIMIT = 200

CHANGED = gnomevfs.MONITOR_EVENT_CHANGED
DELETED = gnomevfs.MONITOR_EVENT_DELETED
CREATED = gnomevfs.MONITOR_EVENT_CREATED

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_DIR_MONITOR, fmt % args)

def event_to_string (event):
    if event == CHANGED:
        return "changed"
    elif event == DELETED:
        return "deleted"
    elif event == CREATED:
        return "created"
    else:
        return "invalid"

class DirectoryMonitor:
    def __init__ (self, directory, callback, data = None):
        self.directory = directory
        self.callback = callback
        self.data = data
        self.watches = {} # maps filename => gnome_vfs_monitor handle
        self.too_many_watches = False
        self.dirs_to_ignore = []
        self.files_to_ignore = []

    def set_directories_to_ignore (self, dirs):
        assert len (self.watches) == 0
        self.dirs_to_ignore = dirs
        dprint ("Ignoring directories %s", self.dirs_to_ignore)

    def set_files_to_ignore (self, files):
        assert len (self.watches) == 0
        self.files_to_ignore = files
        dprint ("Ignoring files %s", self.files_to_ignore)

    #
    # call the user level processing
    #
    def __invoke_callback (self, path, event):
        dprint ("Invoking callback for %s - %s", path, event_to_string (event))
        if self.data:
            self.callback (path, event, self.data)
        else:
            self.callback (path, event)

    #
    # Processing of a gnomevfs callback
    #
    def __handle_gnomevfs_event (self, dir_uri, file_uri, event):
        if event == CHANGED or event == DELETED or event == CREATED:
            # Strip 'file://' and replace %xx with equivalent characters.
            path = file_uri [7:]
            path = urllib.unquote (path)

            # Strip trailing '/'.
            path = os.path.normpath (path)
            
            dprint ("Got gnomevfs event '%s' on '%s'", event_to_string (event), path)

            if not self.__should_ignore_dir (path) and \
               not self.__should_ignore_file (path):
                self.__invoke_callback (path, event)

                if event == CREATED and os.path.isdir (path):
                    self.__monitor_dir_recurse (path, True)
                elif event == DELETED:
                    if path != self.directory and self.watches.has_key (path):
                        dprint ("Deleting watch for '%s' since it got deleted", path)
                        gnomevfs.monitor_cancel (self.watches [path])
                        del self.watches[path]
                        if len (self.watches) < N_WATCHES_LIMIT:
                            self.too_many_watches = False
            else:
                dprint ("Not calling callback for '%s' nor recursing in it since it is an ignored dir/file", path)

    def __should_ignore_dir (self, dir):
        return util.should_ignore_dir (self.directory, self.dirs_to_ignore, dir)
    
    def __should_ignore_file (self, file):
        return util.should_ignore_file (self.directory, self.dirs_to_ignore, self.files_to_ignore, file)

    def __monitor_dir (self, dir):
        dir = os.path.normpath (dir)
        
        if len (self.watches) >= N_WATCHES_LIMIT:
            if not self.too_many_watches:
                print "Too many directories to watch on %s" % (self.directory)
                self.too_many_watches = True
            return

        try:
            self.watches [dir] = gnomevfs.monitor_add (dir, gnomevfs.MONITOR_DIRECTORY, self.__handle_gnomevfs_event)
            dprint ("Added directory watch for '%s'", dir)
        except:
            print ("Failed to add monitor for %s") % (dir)
            util.print_exception ()

    def __monitor_dir_recurse (self, dir, new_dir = False):
        if self.too_many_watches:
            dprint ("Skipping recursion on '%s', as there are already too many watches", dir)
            return

        if self.__should_ignore_dir (dir):
            dprint ("Skipping recursion on '%s'; it is an ignored directory", dir)
            return

        if dir != self.directory:
            self.__monitor_dir (dir)

        for entry in os.listdir (dir):
            path = os.path.join (dir, entry)
            if self.__should_ignore_dir (path) or \
               self.__should_ignore_file (path):
                dprint ("Skipping callback and recursion on '%s'; it is an ignored file/dir", path)
                continue

            self.__invoke_callback (path, CREATED)

            if os.path.isdir (path):
                self.__monitor_dir_recurse (path, new_dir)
                    
    def start (self):
        dprint ("Starting to recursively monitor '%s'", self.directory)
        self.__monitor_dir (self.directory)
        self.__monitor_dir_recurse (self.directory)
        dprint ("Ending recursive scan of '%s'; all monitors are in place now", self.directory)

    def stop (self):
        dprint ("Stopping recursive monitoring of '%s'", self.directory)

        for path in self.watches:
            gnomevfs.monitor_cancel (self.watches [path])

def run_unit_tests ():
    import tempfile
    import shutil

    temp_path = tempfile.mkdtemp (prefix = "test-monitor-")

    def handle_change (path, event, data):
        (expected, main_loop) = data
        if len (expected) > 0:
            i = 0
            for (expected_path, expected_event) in expected:
                if expected_path == path and expected_event == event:
                    break
                i += 1
            if i < len (expected):
                del expected[i]
        if len (expected) == 0:
            main_loop.quit ()

    def expect (expected, path, event):
        expected.append ((path, event))

    main_loop = gobject.MainLoop ()

    expected = []
    def should_not_be_reached (expected):
        for (path, event) in expected:
            print ("Expected event: %s %s") % (path, event_to_string (event))
        assert False
        return True
    timeout = gobject.timeout_add (5 * 1000, should_not_be_reached, expected)

    monitor = DirectoryMonitor (temp_path, handle_change, (expected, main_loop))
    monitor.set_directories_to_ignore (["bar"])
    monitor.set_files_to_ignore (["foobar/foo/foo.txt"])
    monitor.start ()

    expect (expected, os.path.join (temp_path, "foo.txt"), CREATED)
    f = file (os.path.join (temp_path, "foo.txt"), "w")
    f.close ()

    # ignored
    # expect (expected, os.path.join (temp_path, "bar"), CREATED)
    os.mkdir (os.path.join (temp_path, "bar"))

    expect (expected, os.path.join (temp_path, "foobar"), CREATED)
    expect (expected, os.path.join (temp_path, "foobar/foo"), CREATED)
    expect (expected, os.path.join (temp_path, "foobar/foo/bar"), CREATED)
    expect (expected, os.path.join (temp_path, "foobar/foo/bar/foo"), CREATED)
    expect (expected, os.path.join (temp_path, "foobar/foo/bar/foo/bar"), CREATED)
    os.makedirs (os.path.join (temp_path, "foobar/foo/bar/foo/bar"))

    # ignored:
    # expect (expected, os.path.join (temp_path, "foobar/foo/foo.txt"), CREATED)
    f = file (os.path.join (temp_path, "foobar/foo/foo.txt"), "w")
    f.close ()

    main_loop.run ()
    
    expect (expected, os.path.join (temp_path, "foobar/foo/bar/foo/bar"), DELETED)
    expect (expected, os.path.join (temp_path, "foobar/foo/bar/foo"), DELETED)
    expect (expected, os.path.join (temp_path, "foobar/foo/bar"), DELETED)
    # ignored:
    # expect (expected, os.path.join (temp_path, "foobar/foo/foo.txt"), DELETED)
    expect (expected, os.path.join (temp_path, "foobar/foo"), DELETED)
    expect (expected, os.path.join (temp_path, "foobar"), DELETED)
    
    # FIXME: we should be getting this event, but we don't seem to be
    # expect (expected, os.path.join (temp_path, "foo.txt"), DELETED)
    
    # ignore:
    # expect (expected, os.path.join (temp_path, "bar"), DELETED)
    expect (expected, temp_path, DELETED)

    shutil.rmtree (temp_path, True)

    main_loop.run ()

    gobject.source_remove (timeout)

    monitor.stop ()
