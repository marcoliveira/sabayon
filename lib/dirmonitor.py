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
try:
    import gnomevfs
except:
    import gnome.vfs
    import os.path
    gnomevfs = gnome.vfs
    def get_uri_from_local_path(s):
        if s == None:
	    return None
	return "file://" + os.path.abspath(s)
    gnomevfs.__dict__['get_uri_from_local_path'] = get_uri_from_local_path

CHANGED = gnomevfs.MONITOR_EVENT_CHANGED
DELETED = gnomevfs.MONITOR_EVENT_DELETED
CREATED = gnomevfs.MONITOR_EVENT_CREATED

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
        self.monitors = {}
	self.nb_watches = 0

    def __invoke_callback (self, path, event):
        if self.data:
            self.callback (path, event, self.data)
        else:
            self.callback (path, event)

    def __handle_file_event (self, monitor_uri, info_uri, event):
        if event == gnomevfs.MONITOR_EVENT_STARTEXECUTING or \
           event == gnomevfs.MONITOR_EVENT_STOPEXECUTING:
            return

        path = gnomevfs.get_local_path_from_uri (info_uri)
        
        if event == CREATED and os.path.isdir (path):
            self.__monitor_dir_recurse (path, True)
        elif event == DELETED:
            if path != self.directory and self.monitors.has_key (path):
                gnomevfs.monitor_cancel (self.monitors[path])
                del self.monitors[path]

        self.__invoke_callback (path, event)
            
    def __monitor_dir (self, dir):
        if self.nb_watches == 200:
	    print "Too many directories to watch on %s" % (self.directory)
	    self.nb_watches = self.nb_watches + 1
	if self.nb_watches > 200:
	    return

        assert not self.monitors.has_key (dir)
        try:
            monitor = gnomevfs.monitor_add (gnomevfs.get_uri_from_local_path (dir),
                                            gnomevfs.MONITOR_DIRECTORY,
                                            self.__handle_file_event)
        except:
            print "Failed to add monitor for %s" % (dir)
	    import util
	    util.print_exception()
            return
        self.monitors[dir] = monitor
	self.nb_watches = self.nb_watches + 1


    def __monitor_dir_recurse (self, dir, new_dir = False):
        if self.nb_watches > 200:
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
        self.__monitor_dir (self.directory)
        self.__monitor_dir_recurse (self.directory)

    def stop (self):
        for dir in self.monitors:
            gnomevfs.monitor_cancel (self.monitors[dir])
        self.monitors.clear ()

def run_unit_tests ():
    import gobject
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

    f = file (temp_path + "/foo", "w")
    f.close ()
    expect (expected, temp_path + "/foo", CREATED)
    
    os.mkdir (temp_path + "/bar")
    expect (expected, temp_path + "/bar", CREATED)

    os.makedirs (temp_path + "/foobar/foo/bar/foo/bar")
    expect (expected, temp_path + "/foobar", CREATED)
    expect (expected, temp_path + "/foobar/foo", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar/foo", CREATED)
    expect (expected, temp_path + "/foobar/foo/bar/foo/bar", CREATED)
    
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
