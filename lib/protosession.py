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
import sys
import socket
import errno
import signal
import select
import pwd
import commands
import binascii
import struct
import tempfile
import shutil
import gobject
import util
import usermod
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_PROTOSESSION, fmt % args)

class ProtoSessionError (Exception):
    pass

class SessionStartError (ProtoSessionError):
    pass

class XauthParseError (ProtoSessionError):
    pass

#
# These functions are run as root in order to prepare to launch the session
#
def setup_shell_and_homedir (username):
    assert os.geteuid () == 0
    
    pw = pwd.getpwnam (username)
        
    dprint ("Setting shell for '%s' to '%s'", username, DEFAULT_SHELL)
    usermod.set_shell (username, DEFAULT_SHELL)

    temp_homedir = usermod.create_temporary_homedir (pw.pw_uid, pw.pw_gid)
    dprint ("Setting temporary home directory for '%s' to '%s'", username, temp_homedir)
    usermod.set_homedir (username, temp_homedir)

    return temp_homedir
        
def reset_shell_and_homedir (username, temp_homedir):
    assert os.geteuid () == 0
    
    pw = pwd.getpwnam (username)
    
    dprint ("Unsetting homedir for '%s'", username)
    usermod.set_homedir (username, "")

    dprint ("Deleting temporary homedir '%s'", temp_homedir)
    shutil.rmtree (temp_homedir)
        
    dprint ("Resetting shell for '%s' to '%s'", username, NOLOGIN_SHELL)
    usermod.set_shell (username, NOLOGIN_SHELL)

def clobber_user_processes (username):
    assert os.geteuid () == 0
    
    pw = pwd.getpwnam (username)
    
    # FIXME: my, what a big hammer you have!
    argv = CLOBBER_USER_PROCESSES_ARGV + [ pw.pw_name ]
    dprint ("Clobbering existing processes running as user '%s': %s", pw.pw_name, argv)
    util.uninterruptible_spawnv (os.P_WAIT, argv[0], argv)

def find_free_display ():
    def is_display_free (display_number):
        # First make sure we get CONNREFUSED connecting
        # to port 6000 + display_number
        refused = False
        sock = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect (("127.0.0.1", 6000 + display_number))
        except socket.error, (err, errstr):
            if err == errno.ECONNREFUSED:
                refused = True
        
        sock.close ()
        if not refused:
            return False

        # Now make sure either that the lock file doesn't exist or
        # that the server specified in the lock file isn't running
        lock_file = "/tmp/.X%d-lock" % display_number
        if os.path.exists (lock_file):
            f = file (lock_file, "r")
            try:
                pid = int (f.read ())
            except ValueError:
                return False

            process_exists = True
            try:
                os.kill (pid, 0)
            except os.error, (err, errstr):
                if err == errno.ESRCH:
                    process_exists = False
            if process_exists:
                return False

            os.remove (lock_file)
            
        socket_file = "/tmp/.X11-unix/X%d" % display_number
        if os.path.exists (socket_file):
            os.remove (socket_file)

        return True

    display_number = 1
    while display_number < 100:
        if is_display_free (display_number):
            break
        display_number += 1
        
    if display_number == 100:
        raise ProtoSessionError, _("Unable to find a free X display")

    return display_number
        
#
# Everything beyond here gets run from sabayon-session
#
        
def safe_kill (pid, sig):
    try:
        os.kill (pid, sig)
    except os.error, (err, errstr):
        if err != errno.ESRCH:
            raise

class ProtoSession (gobject.GObject):
    __gsignals__ = {
        "finished" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }
    
    def __init__ (self, profile_file, display_number):
        gobject.GObject.__init__ (self)

        self.xauth_cookie = None
        self.profile_file   = profile_file
        self.display_number = display_number
        self.display_name   = ":%s" % display_number

        self.usr1_pipe_r = 0
        self.usr1_pipe_w = 0
        
        self.xnest_pid = 0
        self.xnest_child_watch = 0
        self.xnest_xauth_file = None
        
        self.session_pid = 0
        self.session_child_watch = 0
        self.session_xauth_file = None
        
        self.admin_tool_timeout = 0
        self.admin_tool_pid = 0
        self.admin_tool_child_watch = 0

        self.pw = pwd.getpwuid (os.getuid ())
        
    def __kill_xnest (self):
        if self.xnest_child_watch:
            gobject.source_remove (self.xnest_child_watch)
            self.xnest_child_watch = 0
        
        if self.xnest_pid:
            safe_kill (self.xnest_pid, signal.SIGTERM)
            self.xnest_pid = 0

    def __kill_session (self):
        if self.session_child_watch:
            gobject.source_remove (self.session_child_watch)
            self.session_child_watch = 0
        
        if self.session_pid:
            safe_kill (self.session_pid, signal.SIGTERM)
            self.session_pid = 0

    def __kill_admin_tool (self):
        if self.admin_tool_timeout:
            gobject.source_remove (self.admin_tool_timeout)
            self.admin_tool_timeout = 0
        
        if self.admin_tool_child_watch:
            gobject.source_remove (self.admin_tool_child_watch)
            self.admin_tool_child_watch = 0
        
        if self.admin_tool_pid:
            safe_kill (self.admin_tool_pid, signal.SIGTERM)
            self.admin_tool_pid = 0

    def __del__ (self):
        if self.xnest_xauth_file:
            os.remove (self.xnest_xauth_file)
        if self.session_xauth_file:
            os.remove (self.session_xauth_file)
        if self.usr1_pipe_r:
            os.close (self.usr1_pipe_r)
        if self.usr1_pipe_w:
            os.close (self.usr1_pipe_w)
        self.force_quit ()

    #
    # This USR1 malarky is that if you set the signal handler for
    # SIGUSR1 to SIG_IGN, then the Xserver will send its parent
    # a SIGUSR1 when its ready to start accepting connections.
    #
    def __sigusr1_handler (self, sig, frame):
        self.got_usr1_signal = True
        os.write (self.usr1_pipe_w, "Y")

    def __xnest_child_watch_handler (self, pid, status):
        dprint ("Xnest died")
        
        self.xnest_pid = 0
        self.xnest_child_watch = 0

        self.emit ("finished");
        
        self.force_quit ()

        # If we're waiting for USR1, quit main loop
        if self.main_loop:
            self.main_loop.quit ()
        
        return False

    def __usr1_pipe_watch_handler (self, source, condition):
        dprint ("Got USR1 signal, quitting mainloop")
        self.main_loop.quit ()
        return True

    def __usr1_timeout_handler (self):
        dprint ("Timed out waiting for USR1, quitting mainloop")
        self.main_loop.quit ()
        return True

    # Write out a temporary Xauthority file which contains the same magic
    # cookie as the parent display so that we can pass that using -auth
    # to Xnest.
    #
    # Xauthority is a binary file format:
    #
    #       2 bytes         Family value (second byte is as in protocol HOST)
    #       2 bytes         address length (always MSB first)
    #       A bytes         host address (as in protocol HOST)
    #       2 bytes         display "number" length (always MSB first)
    #       S bytes         display "number" string
    #       2 bytes         name length (always MSB first)
    #       N bytes         authorization name string
    #       2 bytes         data length (always MSB first)
    #       D bytes         authorization data string
    #
    def __write_temp_xauth_file (self, wildcard_addr):
        if self.xauth_cookie == None:
            self.xauth_cookie = util.random_string (16)

        xauth_name = "MIT-MAGIC-COOKIE-1"
        xauth_data = self.xauth_cookie

        if wildcard_addr:
            family = 0xffff # FamilyWild
            display_addr = ""
        else:
            family = 0x0100 # FamilyLocal
            display_addr = socket.gethostname ()

        display_num_str = self.display_number
        display_num_len = len (display_num_str)

        display_addr_len = len (display_addr)
        xauth_name_len   = len (xauth_name)
        xauth_data_len   = len (xauth_data)

        pack_format = ">hh%dsh%dsh%dsh%d" % (display_addr_len, display_num_len, xauth_name_len, xauth_data_len)

        blob = struct.pack (pack_format,
                            family,
                            display_addr_len, display_addr,
                            display_num_len, display_num_str,
                            xauth_name_len, xauth_name,
                            xauth_data_len) + xauth_data

        (fd, temp_xauth_file) = tempfile.mkstemp (prefix = ".xauth-")
        os.write (fd, blob)
        os.close (fd)

        dprint ("Wrote temporary xauth file to %s" % temp_xauth_file)

        return temp_xauth_file

    #
    # Need to hold open the first X connection until the session dies
    #
    def __open_x_connection (self, display_name, xauth_file):
        (pipe_r, pipe_w) = os.pipe ()
        pid = os.fork ()
        if pid == 0: # Child process
            os.close (pipe_r)
            new_environ = os.environ.copy ()
            new_environ["DISPLAY"] = display_name
            new_environ["XAUTHORITY"] = xauth_file
            argv = [ "python", "-c",
                     "import gtk, os, sys; os.write (int (sys.argv[1]), 'Y'); gtk.main ()" ,
                     str (pipe_w) ]
            os.execvpe (argv[0], argv, new_environ)
        os.close (pipe_w)
        while True:
            try:
                select.select ([pipe_r], [], [])
                break
            except select.error, (err, errstr):
                if err != errno.EINTR:
                    raise
        os.close (pipe_r)

    #
    # FIXME: we have a re-entrancy issue here - if while we're
    # runing the mainloop we re-enter, then we'll install another
    # SIGUSR1 handler and everything will break
    #
    def __start_xnest (self, parent_window):
        dprint ("Starting Xnest %s" % self.display_name)

        self.xnest_xauth_file = self.__write_temp_xauth_file (True)

        (self.usr1_pipe_r, self.usr1_pipe_w) = os.pipe ()
        self.got_usr1_signal = False
        signal.signal (signal.SIGUSR1, self.__sigusr1_handler)

        self.xnest_pid = os.fork ()
        if self.xnest_pid == 0: # Child process
            signal.signal (signal.SIGUSR1, signal.SIG_IGN)

            argv = XNEST_ARGV + \
                   [ "-auth", self.xnest_xauth_file ] + \
                   [ "-name", "sabayon" ]
            if parent_window:
                argv += [ "-parent", parent_window ]
            argv += [ self.display_name ]

            dprint ("Child process launching %s" % argv)

            os.execv (argv[0], argv)

            # Shouldn't ever reach here
            sys.stderr.write ("Failed to launch Xnest")
            os._exit (1)

        self.main_loop = gobject.MainLoop ()

        self.xnest_child_watch = gobject.child_watch_add (self.xnest_pid,
                                                          self.__xnest_child_watch_handler)
        io_watch = gobject.io_add_watch (self.usr1_pipe_r,
                                         gobject.IO_IN | gobject.IO_PRI,
                                         self.__usr1_pipe_watch_handler)
        timeout = gobject.timeout_add (XNEST_USR1_TIMEOUT * 1000,
                                       self.__usr1_timeout_handler)

        dprint ("Waiting on child process (%d)" % self.xnest_pid)

        self.main_loop.run ()
        self.main_loop = None

        signal.signal (signal.SIGUSR1, signal.SIG_IGN)

        gobject.source_remove (timeout)
        gobject.source_remove (io_watch)
        
        os.close (self.usr1_pipe_r)
        self.usr1_pipe_r = 0
        os.close (self.usr1_pipe_w)
        self.usr1_pipe_w = 0

        if not self.got_usr1_signal:
            if self.xnest_child_watch:
                gobject.source_remove (self.xnest_child_watch)
                self.xnest_child_watch = 0
            
            if self.xnest_pid:
                safe_kill (self.xnest_pid, signal.SIGTERM)
                self.xnest_pid = 0
                raise SessionStartError, _("Failed to start Xnest: timed out waiting for USR1 signal")
            else:
                raise SessionStartError, _("Failed to start Xnest: died during startup")

    def __session_child_watch_handler (self, pid, status):
        dprint ("Session died")
        
        self.session_pid = 0
        self.session_child_watch = 0

        self.force_quit ()

        self.emit ("finished")
            
        return False

    def __start_session (self):
        dprint ("Starting session")

        self.session_xauth_file = self.__write_temp_xauth_file (False)
        
        self.__open_x_connection (self.display_name, self.session_xauth_file)

        self.session_pid = os.fork ()
        if self.session_pid == 0: # Child process
            new_environ = os.environ.copy ()

            new_environ["DISPLAY"]    = self.display_name
            new_environ["XAUTHORITY"] = self.session_xauth_file

            self.session_xauth_file = None

            # Disable sabayon-xinitrc.sh
            new_environ["DISABLE_SABAYON_XINITRC"] = "yes"

            # Don't allow running Sabayon in the session
            new_environ["SABAYON_SESSION_RUNNING"] = "yes"

            # Disable Xscreensaver locking
            new_environ["RUNNING_UNDER_GDM"] = "yes"

            dprint ("Child process env: %s" % new_environ)
            
            # Start the session
            dprint ("Executing %s" % SESSION_ARGV)
            os.execve (SESSION_ARGV[0], SESSION_ARGV, new_environ)

            # Shouldn't ever happen
            sys.stderr.write ("Failed to launch Xsession")
            os._exit (1)

        self.session_child_watch = gobject.child_watch_add (self.session_pid,
                                                            self.__session_child_watch_handler)

        
    def apply_profile (self):
        argv = APPLY_TOOL_ARGV + [ "-s", self.profile_file ]
        dprint ("Running apply tool: %s" % argv)
        util.uninterruptible_spawnve (os.P_WAIT, argv[0], argv, os.environ.copy ())
    
    def start (self, parent_window):
        # Get an X server going
        self.__start_xnest (parent_window)

        # Start the session
        self.__start_session ()
        
    def force_quit (self):
        self.__kill_session ()
        self.__kill_xnest ()

gobject.type_register (ProtoSession)
