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
import gobject
import gamin
import util

N_WATCHES_LIMIT = 200

CHANGED = gamin.GAMChanged
DELETED = gamin.GAMDeleted
CREATED = gamin.GAMCreated

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_DIRMONITOR, fmt % args)

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
	self.mon = None
	self.watches = {}
        self.too_many_watches = False
	self.fd = -1
	self.io_watch = None
        self.dirs_to_ignore = []
        self.files_to_ignore = []

    def set_directories_to_ignore (self, dirs):
        assert self.mon == None
        self.dirs_to_ignore = dirs
        dprint ("Ignoring directories %s" % self.dirs_to_ignore)

    def set_files_to_ignore (self, files):
        assert self.mon == None
        self.files_to_ignore = files
        dprint ("Ignoring files %s" % self.files_to_ignore)

    #
    # call the user level processing
    #
    def __invoke_callback (self, path, event):
        if self.data:
            self.callback (path, event, self.data)
        else:
            self.callback (path, event)

    #
    # Called from the main loop when we have data
    #
    def __pending_data (self, fd, condition):
	try:
	    ret = self.mon.handle_events ()
	except:
	    util.print_exception ()
	return True
        
    #
    # Processing of a gamin callback
    #
    def __handle_gamin_event (self, path, event, monitor_file):
        if event == CHANGED or event == DELETED or event == CREATED:
            if not os.path.isabs (path):
		path = monitor_file + '/' + path

            dprint ("Got gamin event '%s' on '%s'" % (event_to_string (event), path))

	    if event == CREATED and os.path.isdir (path):
		self.__monitor_dir_recurse (path, True)
	    elif event == DELETED:
                if path != self.directory and self.watches.has_key (path):
                    del self.watches[path]
                    if len (self.watches) < N_WATCHES_LIMIT:
                        self.too_many_watches = False
                    self.mon.stop_watch (path)

            if not self.__should_ignore_dir (path) and \
               not self.__should_ignore_file (path):
                self.__invoke_callback (path, event)

    def __should_ignore_dir (self, dir):
        for ignore_dir in self.dirs_to_ignore:
            if dir == self.directory + "/" + ignore_dir:
                dprint ("Ignoring directory '%s'" % (dir))
                return True
        return False
    
    def __should_ignore_file (self, file):
        for ignore_file in self.files_to_ignore:
            if file == self.directory + "/" + ignore_file:
                dprint ("Ignoring file '%s'" % (file))
                return True
        return False

    def __monitor_dir (self, dir):
        if len (self.watches) >= N_WATCHES_LIMIT:
            if not self.too_many_watches:
                print "Too many directories to watch on %s" % (self.directory)
                self.too_many_watches = True
            return

        if self.__should_ignore_dir (dir):
            return
        
        try:
            self.mon.watch_directory (dir, self.__handle_gamin_event, dir)
        except:
            print "Failed to add monitor for %s" % (dir)
	    util.print_exception ()

    def __monitor_dir_recurse (self, dir, new_dir = False):
        if self.too_many_watches:
            return
        if dir != self.directory:
            self.__monitor_dir (dir)
        for entry in os.listdir (dir):
            path = dir + "/" + entry
            if self.__should_ignore_dir (path) or \
               self.__should_ignore_file (path):
                continue
            if new_dir:
                self.__invoke_callback (path, CREATED)
            if os.path.isdir (path):
                self.__monitor_dir_recurse (path, new_dir)
                    
    def start (self):
        if self.mon != None:
	    return

        dprint ("Starting to recursively monitor '%s'" % self.directory)

	self.mon = gamin.WatchMonitor ()
	# ignore (End)Exists events since we scan the tree ourselves
	try:
	    self.mon.no_exists ()
	except:
	    pass
	self.fd = self.mon.get_fd ()
	self.io_watch = gobject.io_add_watch (self.fd,
                                              gobject.IO_IN|gobject.IO_PRI,
                                              self.__pending_data)
        self.__monitor_dir (self.directory)
        self.__monitor_dir_recurse (self.directory)

    def stop (self):
        if self.mon == None:
	    return

        dprint ("Stopping recursive monitoring of '%s'" % self.directory)

        for path in self.watches:
            self.mon.stop_watch (path)
        
        gobject.source_remove (self.io_watch)
	self.io_watch = 0
        
	self.mon.disconnect ()
	self.mon = None
	self.fd = -1

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
            print "Expected event: %s %s" % (path, event_to_string (event))
        assert False
        return True
    timeout = gobject.timeout_add (5 * 1000, should_not_be_reached, expected)

    monitor = DirectoryMonitor (temp_path, handle_change, (expected, main_loop))
    monitor.set_directories_to_ignore (["bar"])
    monitor.set_files_to_ignore (["foobar/foo/foo.txt"])
    monitor.start ()

    expect (expected, temp_path + "/foo.txt", CREATED)
    f = file (temp_path + "/foo.txt", "w")
    f.close ()

    # ignored
    # expect (expected, temp_path + "/bar", CREATED)
    os.mkdir (temp_path + "/bar")

    expect (expected, temp_path + "/foobar", CREATED)
    expect (expected, temp_path + "/foobar/foo", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar/foo", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar/foo/bar", CREATED)
    os.makedirs (temp_path + "/foobar/foo/bar/foo/bar")

    # ignored:
    # expect (expected, temp_path + "/foobar/foo/foo.txt", CREATED)
    f = file (temp_path + "/foobar/foo/foo.txt", "w")
    f.close ()

    main_loop.run ()
    
    expect (expected, temp_path + "/foobar/foo/bar/foo/bar", DELETED)
    expect (expected, temp_path + "/foobar/foo/bar/foo", DELETED)
    expect (expected, temp_path + "/foobar/foo/bar", DELETED)
    # ignored:
    # expect (expected, temp_path + "/foobar/foo/foo.txt", DELETED)
    expect (expected, temp_path + "/foobar/foo", DELETED)
    expect (expected, temp_path + "/foobar", DELETED)
    expect (expected, temp_path + "/foo.txt", DELETED)
    # ignore:
    # expect (expected, temp_path + "/bar", DELETED)
    expect (expected, temp_path, DELETED)

    shutil.rmtree (temp_path, True)

    main_loop.run ()

    gobject.source_remove (timeout)

    monitor.stop ()

if __name__ == '__main__':
    run_unit_tests()

