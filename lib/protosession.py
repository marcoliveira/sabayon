#!/usr/bin/env python

import os
import os.path
import socket
import errno
import signal
import pwd
import gobject

XNEST_ARGV = [ "/usr/X11R6/bin/Xnest", "-audit", "0", "-name", "Xnest", "-nolisten", "tcp" ]
#SESSION_ARGV = [ "/etc/X11/xdm/Xsession", "gnome" ]
SESSION_ARGV = [ "/usr/bin/gnome-terminal" ]
DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/X11R6/bin"

class ProtoSessionError (Exception):
    pass

class SessionStartError (ProtoSessionError):
    pass

def __safe_kill (pid, sig):
    try:
        os.kill (pid, sig)
    except os.error, (err, str):
        if err != errno.ESRCH:
            rasie

class ProtoSession (gobject.GObject):
    __gsignals__ = {
        "finished" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }
    
    def __init__ (self, username):
        gobject.GObject.__init__ (self)
        assert os.geteuid () == 0
        self.username = username
        self.usr1_pipe_r = 0
        self.usr1_pipe_w = 0
        self.xnest_pid = 0
        self.session_pid = 0
        self.xnest_child_watch = 0
        self.session_child_watch = 0

    def __del__ (self):
        if self.usr1_pipe_r:
            close (self.usr1_pipe_r)
        if self.usr1_pipe_w:
            close (self.usr1_pipe_w)
        self.force_quit ()

    def __is_display_free (self, display_number):
        # First make sure we get CONNREFUSED connecting
        # to port 6000 + display_number
        refused = False
        sock = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect (("127.0.0.1", 6000 + display_number))
        except socket.error, (err, str):
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
            except os.error, (err, str):
                if err == errno.ESRCH:
                    process_exists = False
            if process_exists:
                return False

        return True

    def __find_free_display (self):
        display_number = 1
        while display_number < 100:
            if self.__is_display_free (display_number):
                return display_number
            display_number += 1
        return -1

    #
    # This USR1 malarky is that if you set the signal handler for
    # SIGUSR1 to SIG_IGN, then the Xserver will send its parent
    # a SIGUSR1 when its ready to start accepting connections.
    #
    def __sigusr1_handler (self, sig, frame):
        self.got_usr1_signal = True
        os.write (self.usr1_pipe_w, "Y")

    def __xnest_child_watch_handler (self, pid, status):
        self.xnest_pid = 0
        self.xnest_child_watch = 0

        if self.session_child_watch:
            gobject.source_remove (self.session_child_watch)
            self.session_child_watch = 0

        if self.session_pid:
            __safe_kill (self.session_pid, signal.SIGTERM)
            self.session_pid = 0
        
        if self.main_loop:
            self.main_loop.quit ()
        return False

    def __usr1_pipe_watch_handler (self, source, condition):
        self.main_loop.quit ()
        return True

    def __usr1_timeout_handler (self):
        self.main_loop.quit ()
        return True
    
    #
    # FIXME: we have a re-entrancy issue here - if while we're
    # runing the mainloop we re-enter, then we'll install another
    # SIGUSR1 handler and everything will break
    #
    def __start_xnest (self):
        self.display_number = self.__find_free_display ()
        if self.display_number == -1:
            raise SessionStartError, "Unable to find a free X display"

        self.display_name = ":%d" % self.display_number

        (self.usr1_pipe_r, self.usr1_pipe_w) = os.pipe ()
        self.got_usr1_signal = False
        signal.signal (signal.SIGUSR1, self.__sigusr1_handler)

        self.xnest_pid = os.fork ()
        if self.xnest_pid == 0: # Child process
            signal.signal (signal.SIGUSR1, signal.SIG_IGN)
            
            argv = XNEST_ARGV + [ self.display_name ]

            os.execv (argv[0], argv)

            # Shouldn't ever reach here
            print "Failed to launch Xnest"
            os._exit (1)

        self.main_loop = gobject.MainLoop ()

        self.xnest_child_watch = gobject.child_watch_add (self.xnest_pid,
                                                          self.__xnest_child_watch_handler)
        io_watch = gobject.io_add_watch (self.usr1_pipe_r,
                                         gobject.IO_IN | gobject.IO_PRI,
                                         self.__usr1_pipe_watch_handler)
        timeout = gobject.timeout_add (5 * 1000,
                                       self.__usr1_timeout_handler)

        self.main_loop.run ()
        self.main_loop = None

        signal.signal (signal.SIGUSR1, signal.SIG_IGN)

        gobject.source_remove (timeout_watch)
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
                __safe_kill (self.xnest_pid, signal.SIGTERM)
                self.xnest_pid = 0
                raise SessionStartError, "Failed to start Xnest: timed out waiting for USR1 signal"
            else:
                raise SessionStartError, "Failed to start Xnest: died during startup"

    def __session_child_watch_handler (self, pid, status):
        self.session_pid = 0
        self.session_child_watch = 0

        if self.xnest_child_watch:
            gobject.source_remove (self.xnest_child_watch)
            self.xnest_child_watch = 0

        if self.xnest_pid:
            __safe_kill (self.xnest_pid, signal.SIGTERM)
            self.xnest_pid = 0

        self.emit ("finished")
            
        return False

    def __start_session (self):
        try:
            pw = pwd.getpwnam (self.username)
        except KeyError:
            raise SessionStartError, "User '%s' does not exist" % self.username

        if pw.pw_dir == "" or not os.path.isdir (pw.pw_dir):
            raise SessionStartError, "Home directory for user '%s' does not exist" % self.username

        self.session_pid = os.fork ()
        if self.session_pid == 0: # Child process
            os.setgid (pw.pw_gid)
            os.setuid (pw.pw_uid)

            os.chdir (pw.pw_dir)

            # FIXME: need to setup X cookie
            # FIXME: setting the selinux context?

            new_environ = {}
            for key in os.environ:
                if key.startswith ("LC_") or \
                   key == "LANG" or \
                   key == "LINGUAS":
                    new_environ[key] = os.environ[key]

                if key == "XAUTHORITY": # FIXME: remove
                    new_environ[key] = os.environ[key]

            os.environ = new_environ
    
            os.environ["PATH"]       = DEFAULT_PATH 
            # os.environ["XAUTHORITY"] = "" # FIXME
            os.environ["DISPLAY"]    = self.display_name
            os.environ["LOGNAME"]    = pw.pw_name
            os.environ["USER"]       = pw.pw_name
            os.environ["USERNAME"]   = pw.pw_name
            os.environ["HOME"]       = pw.pw_dir
            os.environ["SHELL"]      = pw.pw_shell

            os.setsid ()
            os.umask (022)
    
            os.execv (SESSION_ARGV[0], SESSION_ARGV)

            # Shouldn't ever happen
            print "Failed to launch Xsession"
            os._exit (1)

        self.session_child_watch = gobject.child_watch_add (self.session_pid,
                                                            self.__session_child_watch_handler)

    def start (self):
        self.__start_xnest ()
        
        # At this point, we should be able to connect to Xnest
        self.__start_session ()

    def force_quit (self):
        if self.xnest_child_watch:
            gobject.source_remove (self.xnest_child_watch)
            self.xnest_child_watch = 0
        
        if self.session_child_watch:
            gobject.source_remove (self.session_child_watch)
            self.session_child_watch = 0

        if self.xnest_pid:
            __safe_kill (self.xnest_pid, signal.SIGTERM)
            self.xnest_pid = 0
        
        if self.session_pid:
            __safe_kill (self.session_pid, signal.SIGTERM)
            self.session_pid = 0

gobject.type_register (ProtoSession)


#
# Unit tests
#
def run_unit_tests ():
    pass
