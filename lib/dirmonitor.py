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

N_WATCHES_LIMIT = 200

CHANGED = gamin.GAMChanged
DELETED = gamin.GAMDeleted
CREATED = gamin.GAMCreated

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
    def __pending_data(self, foo = None, bar = None):
	try:
	    ret = self.mon.handle_events()
	except:
	    import util
	    util.print_exception()
	return True
        
    #
    # Processing of a gamin callback
    #
    def __handle_gamin_event (self, path, event, monitor_file):
        if event == CHANGED or event == DELETED or event == CREATED:
            if not os.path.isabs (path):
		path = monitor_file + '/' + path

	    if event == CREATED and os.path.isdir (path):
		self.__monitor_dir_recurse (path, True)
	    elif event == DELETED:
                if path != self.directory and self.watches.has_key (path):
                    del self.watches[path]
                    if len (self.watches) < N_WATCHES_LIMIT:
                        self.too_many_watches = False
                    self.mon.stop_watch(path)

            self.__invoke_callback (path, event)

    def __monitor_dir (self, dir):
        if len (self.watches) >= N_WATCHES_LIMIT:
            if not self.too_many_watches:
                print "Too many directories to watch on %s" % (self.directory)
                self.too_many_watches = True
            return

        try:
            self.mon.watch_directory(dir, self.__handle_gamin_event, dir)
        except:
            print "Failed to add monitor for %s" % (dir)
	    import util
	    util.print_exception()
            return

    def __monitor_dir_recurse (self, dir, new_dir = False):
        if self.too_many_watches:
            return
        if dir != self.directory:
            self.__monitor_dir (dir)
        for entry in os.listdir (dir):
            path = dir + "/" + entry
            if new_dir:
                self.__invoke_callback (path, CREATED)
            if os.path.isdir (path):
                self.__monitor_dir_recurse (path, new_dir)
                    
    def start (self):
        if self.mon != None:
	    return

	self.mon = gamin.WatchMonitor()
	self.fd = self.mon.get_fd()
	self.io_watch = gobject.io_add_watch (self.fd, gobject.IO_IN,
                                              self.__pending_data)
        self.__monitor_dir (self.directory)
        self.__monitor_dir_recurse (self.directory)

    def stop (self):
        if self.mon == None:
	    return

        gobject.source_remove(self.io_watch)
	self.io_watch = 0
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

    def should_not_be_reached ():
        assert False
        return True
    timeout = gobject.timeout_add (5 * 1000, should_not_be_reached)

    expected = []
    monitor = DirectoryMonitor (temp_path, handle_change, (expected, main_loop))
    monitor.start ()

    expect (expected, temp_path + "/foo", CREATED)
    f = file (temp_path + "/foo", "w")
    f.close ()
    
    expect (expected, temp_path + "/bar", CREATED)
    os.mkdir (temp_path + "/bar")

    expect (expected, temp_path + "/foobar", CREATED)
    expect (expected, temp_path + "/foobar/foo", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar/foo", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar/foo/bar", CREATED)
    os.makedirs (temp_path + "/foobar/foo/bar/foo/bar")
    
    main_loop.run ()
    
    expect (expected, temp_path + "/foobar/foo/bar/foo/bar", DELETED)
    expect (expected, temp_path + "/foobar/foo/bar/foo", DELETED)
    expect (expected, temp_path + "/foobar/foo/bar", DELETED)
    expect (expected, temp_path + "/foobar/foo", DELETED)
    expect (expected, temp_path + "/foobar", DELETED)
    expect (expected, temp_path + "/foo", DELETED)
    expect (expected, temp_path + "/bar", DELETED)
    expect (expected, temp_path, DELETED)

    shutil.rmtree (temp_path, True)

    main_loop.run ()

    gobject.source_remove (timeout)

if __name__ == '__main__':
    run_unit_tests()

