#!/usr/bin/env python

import os
import os.path
import socket
import errno
import signal
import pwd
import gobject
import util

XNEST_ARGV = [ "/usr/X11R6/bin/Xnest", "-audit", "0", "-name", "Xnest", "-nolisten", "tcp" ]
#SESSION_ARGV = [ "/etc/X11/xdm/Xsession", "gnome" ]
SESSION_ARGV = [ "/usr/bin/gnome-terminal" ]
DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/X11R6/bin"

class ProtoSessionError (Exception):
    pass

class SessionStartError (ProtoSessionError):
    pass

class XauthParseError (ProtoSessionError):
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
        # FIXME: delete xauth files
        # self.session_xauth_file
        # self.xnest_xauth_file
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

    def __get_xauth_record (self):
        (status, output) = commands.getstatusoutput ("xauth -in list $DISPLAY")
        if status != 0:
            raise XauthParseError, "'xauth list' returned error"

        for line in output.split ("\n"):
            fields = line.split ("  ")
            if len (fields) == 3 and len (fields[2]) % 2 == 0:
                return (fields[1], binascii.unhexlify (fields[2]))
        
        raise XauthParseError, "'xauth list' returned no records or records in unknown format"

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
    def __write_temp_xauth_file (self):
        (xauth_name, xauth_data) = self.__get_xauth_record ()
        
        display_num_str = str (self.display_number)
        display_num_len = len (display_num_str)

        xauth_name_len = len (xauth_name)
        xauth_data_len = len (xauth_data)

        pack_format = ">hh0sh%dsh%dsh%d" % (display_num_len, xauth_name_len, xauth_data_len)

        blob = struct.pack (pack_format,
                            0xffff, # FamilyWild
                            0, "",  # address
                            display_num_len, display_num_str,
                            xauth_name_len, xauth_name,
                            xauth_data_len) + xauth_data

        (fd, temp_xauth_file) = tempfile.mkstemp (prefix = ".xauth-")
        os.write (fd, blob)
        os.close (fd)

        return temp_xauth_file

    def __copy_xauth_file (self, uid, gid):
        if os.environ.has_key ("XAUTHORITY"):
            xauth_file = os.environ["XAUTHORITY"]
        else:
            xauth_file = util.get_home_dir () + "/.Xauthority"

        try:
            handle = file (xauth_file, "r")
        except IOError, (err, str):
            raise SessionStartError, "Unable to locate Xauthority file '%s': %s" % (xauth_file, str)
        
        (fd, xauth_copy) = tempfile.mkstemp (prefix = ".Xauthority")

        for line in file:
            os.write (fd, line)
        os.close (fd)
        file.close ()

        os.chown (xauth_copy, uid, gid)

        return xauth_copy
        
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

        self.xnest_xauth_file = self.__write_temp_xauth_file ()

        (self.usr1_pipe_r, self.usr1_pipe_w) = os.pipe ()
        self.got_usr1_signal = False
        signal.signal (signal.SIGUSR1, self.__sigusr1_handler)

        self.xnest_pid = os.fork ()
        if self.xnest_pid == 0: # Child process
            signal.signal (signal.SIGUSR1, signal.SIG_IGN)

            argv = XNEST_ARGV + [ "-auth", self.xnest_xauth_file ]
            argv += [ self.display_name ]

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

        self.session_xauth_file = self.__copy_xauth_file (pw.pw_uid, pw.pw_gid)
        
        self.session_pid = os.fork ()
        if self.session_pid == 0: # Child process
            os.setgid (pw.pw_gid)
            os.setuid (pw.pw_uid)

            os.chdir (pw.pw_dir)

            # FIXME: setting the selinux context?

            new_environ = {}
            for key in os.environ:
                if key.startswith ("LC_") or \
                   key == "LANG" or \
                   key == "LINGUAS":
                    new_environ[key] = os.environ[key]

            os.environ = new_environ
    
            os.environ["PATH"]       = DEFAULT_PATH 
            os.environ["DISPLAY"]    = self.display_name
            os.environ["XAUTHORITY"] = self.session_xauth_file
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

        # FIXME: need to apply profile before starting session
        
        # At this point, we should be able to connect to Xnest
        self.__start_session ()

        # FIXME: need to run the change viewer tool

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
