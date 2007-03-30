import math
import os
import sys
import threading
import time
import traceback
import warnings
import exceptions
import ConfigParser
import util

DEBUG_LOG_DOMAIN_USER = "USER"

DEBUG_LOG_DOMAIN_SABAYON_APPLY   = "sabayon-apply"
DEBUG_LOG_DOMAIN_SABAYON_SESSION = "sabayon-session"
DEBUG_LOG_DOMAIN_DEPRECATED      = "deprecated"
DEBUG_LOG_DOMAIN_USER_PROFILE    = "user-profile"
DEBUG_LOG_DOMAIN_STORAGE         = "storage"
DEBUG_LOG_DOMAIN_PROTO_SESSION   = "proto-session"
DEBUG_LOG_DOMAIN_USERMOD         = "usermod"
DEBUG_LOG_DOMAIN_DIR_MONITOR     = "dir-monitor"
DEBUG_LOG_DOMAIN_GCONF_SOURCE    = "gconf-source"
DEBUG_LOG_DOMAIN_PANEL_DELEGATE  = "panel-delegate"
DEBUG_LOG_DOMAIN_FILES_SOURCE    = "files-source"
DEBUG_LOG_DOMAIN_MOZILLA_SOURCE  = "mozilla-source"
DEBUG_LOG_DOMAIN_ADMIN_TOOL      = "admin-tool"
DEBUG_LOG_DOMAIN_USER_DB         = "user-db"
DEBUG_LOG_DOMAIN_CACHE           = "cache"

_debug_log_log = None
_debug_log_the_lock = threading.Lock ()

def uprint (fmt, *args):
    """Logs a non-milestone message in the USER domain.
    @fmt: Format string for message.
    @args: Arguments for format string."""
    debug_log (False, DEBUG_LOG_DOMAIN_USER, fmt % args)

class DebugLog:
    """This class is internal.  Use the following functions instead:
    debug_log()
    debug_log_current_exception()
    debug_log_load_configuration()
    debug_log_is_domain_enabled()
    debug_log_dump_as_list()
    debug_log_dump_to_file()
    debug_log_dump_configuration()"""

    SECTION_DEBUG_LOG = "debug log"
    KEY_ENABLE_DOMAINS = "enable domains"
    KEY_MAX_LINES = "max lines"

    DEFAULT_MAX_LINES = 1000

    def __init__ (self):
        self.domains = {}
        self.ring_buffer = None
        self.ring_max_lines = self.DEFAULT_MAX_LINES
        self.ring_next_index = 0
        self.ring_num_lines = 0

        self.milestones = []

    def ensure_ring_buffer (self):
        if self.ring_buffer:
            return

        self.ring_buffer = list (range (self.ring_max_lines))
        self.ring_next_index = 0
        self.ring_num_lines = 0

    def is_domain_enabled (self, domain):
        return domain == DEBUG_LOG_DOMAIN_USER or self.domains.has_key (domain)

    def add_to_ring (self, msg):
        self.ensure_ring_buffer ()

        if self.ring_num_lines < self.ring_max_lines:
            self.ring_num_lines = self.ring_num_lines + 1

        self.ring_buffer[self.ring_next_index] = msg

        self.ring_next_index = self.ring_next_index + 1
        if self.ring_next_index == self.ring_max_lines:
            self.ring_next_index = 0
            assert self.ring_num_lines == self.ring_max_lines

    def add_to_milestones (self, msg):
        self.milestones.append (msg)

    def enable_domain (self, domain):
        if domain == DEBUG_LOG_DOMAIN_USER:
            return # user actions are always enabled

        self.domains[domain] = True

    def disable_domain (self, domain):
        if domain == DEBUG_LOG_DOMAIN_USER:
            return # user actions are always enabled

        if self.domains.has_key (domain):
            del self.domains[domain]

    def enable_domains_from_string (self, s):
        raw_domains = s.split (";") # use the same separator as GKeyFile from Glib
        for d in raw_domains:
            d = d.strip ()
            if d != "":
                self.enable_domain (d)

    def set_max_lines (self, num_lines):
        if num_lines < 1:
            raise ValueError ("num_lines must be 1 or greater")

        if num_lines == self.ring_max_lines:
            return

        new_ring = list (range (num_lines))
        lines_to_copy = min (num_lines, self.ring_num_lines)

        if self.ring_num_lines == self.ring_max_lines:
            start_index = (self.ring_next_index + self.ring_max_lines - lines_to_copy) % self.ring_max_lines
        else:
            start_index = self.ring_num_lines - lines_to_copy

        assert start_index >= 0 and start_index < self.ring_max_lines

        for i in range (lines_to_copy):
            idx = (start_index + i) & self.ring_max_lines
            new_ring[i] = self.ring_buffer[idx]

        self.ring_buffer = new_ring
        self.ring_next_index = lines_to_copy
        self.ring_num_lines = lines_to_copy
        self.ring_max_lines = num_lines

    def set_max_lines_from_string (self, s):
        valid = False
        try:
            i = int (s)
            valid = True
        except:
            pass

        if valid:
            self.set_max_lines (i)

    def load_configuration (self, filename):
        config = ConfigParser.ConfigParser ()

        config.read (filename)

        if config.has_option (self.SECTION_DEBUG_LOG, self.KEY_ENABLE_DOMAINS):
            self.enable_domains_from_string (config.get (self.SECTION_DEBUG_LOG, self.KEY_ENABLE_DOMAINS))

        if config.has_option (self.SECTION_DEBUG_LOG, self.KEY_MAX_LINES):
            self.set_max_lines_from_string (config.get (self.SECTION_DEBUG_LOG, self.KEY_MAX_LINES))

    def dump_configuration (self, file):
        file.write (self.make_configuration_string ())

    def make_configuration_string (self):
        config_str = "[%s]\n%s = %s\n" % (self.SECTION_DEBUG_LOG, self.KEY_MAX_LINES, self.ring_max_lines)

        if len (self.domains) > 0:
            domains = self.domains.keys ()
            str_domains = ";".join (domains)
            config_str = config_str + ("\n%s = %s\n" % (self.KEY_ENABLE_DOMAINS, str_domains))

        return config_str

    def dump_configuration_to_list (self, list, config_filename):
        list.extend (["\n\n",
                      "This configuration for the debug log can be re-created\n",
                      "by putting the following in %s\n" % config_filename,
                      "(use ';' to separate domain names):\n\n"])

        list.append (self.make_configuration_string ())

    def dump_milestones_to_list (self, list, config_filename):
        list.append ("===== BEGIN MILESTONES =====\n")

        for s in self.milestones:
            list.append (s + "\n")

        list.append ("===== END MILESTONES =====\n")

    def dump_ring_buffer_to_list (self, list, config_):
        list.append ("===== BEGIN RING BUFFER =====\n")

        if self.ring_num_lines == self.ring_max_lines:
            start_index = self.ring_next_index
        else:
            start_index = 0

        for i in range (self.ring_num_lines):
            idx = (start_index + i) % self.ring_max_lines
            list.append (self.ring_buffer[idx] + "\n")

        list.append ("===== END RING BUFFER =====\n")

    def dump_to_list (self, list, config_filename):
        self.dump_milestones_to_list (list, config_filename)
        self.dump_ring_buffer_to_list (list, config_filename)
        self.dump_configuration_to_list (list, config_filename)

    def clear (self):
        self.ring_next_index = 0
        self.ring_num_lines = 0

def _debug_log_lock ():
    global _debug_log_log

    _debug_log_the_lock.acquire ()

    if not _debug_log_log:
        _debug_log_log = DebugLog () # FIXME: do this here or in a debug_lock_init() function?

def _debug_log_unlock ():
    _debug_log_the_lock.release ()

def debug_log (is_milestone, domain, msg):
    """Logs a message to the debug log.

    @is_milestone: If True, the message will be logged unconditionally.  If False, the message
    will only be logged if the specified log domain was enabled when reading the configuration
    with debug_log_load_configuration().
    @domain: The log domain, which determines whether a message is logged or not.
    The "USER" domain is always enabled.
    @msg: Message to log."""

    global _debug_log_log

    if type (domain) != str:
        raise TypeError ("domain must be a string")

    if type (msg) != str:
        raise TypeError ("msg must be a string")

    _debug_log_lock ()
    try:
        if not (is_milestone or _debug_log_log.is_domain_enabled (domain)):
            return

        thread = threading.currentThread ()
        timestamp = time.time ()
        t = time.localtime (timestamp)

        msg = ("%s %04d/%02d/%02d %02d:%02d:%02d.%04d (%s): %s" %
               (thread.getName (),
                t.tm_year, t.tm_mon, t.tm_mday,
                t.tm_hour, t.tm_min, t.tm_sec, int (math.fmod (timestamp, 1.0) * 10000),
                domain,
                msg))

        _debug_log_log.add_to_ring (msg)

        if is_milestone:
            _debug_log_log.add_to_milestones (msg)

        print msg
    finally:
        _debug_log_unlock ()

def debug_log_current_exception (domain):
    """Logs the current exception as a milestone.

    @domain: Domain in which to log the exception.  This is only used for informational
    purposes, since the exception will always be logged (it's a milestone)."""

    # Exceptions are always logged as milestones
    debug_log (True, domain, traceback.format_exc ())

def debug_log_load_configuration (config_filename):
    """Loads the configuration for the debug log from a file.  Does nothing if the file
    does not exist or if it is unreadable.

    @config_filename: Name of the file from which to read the configuration."""

    global _debug_log_log

    if config_filename != None and type (config_filename) != str:
        raise TypeError ("config_filename must be a string or None")

    _debug_log_lock ()
    try:
        if config_filename:
            _debug_log_log.load_configuration (config_filename)

        if not _debug_log_log.is_domain_enabled (DEBUG_LOG_DOMAIN_DEPRECATED):
            warnings.filterwarnings ("ignore", category = exceptions.DeprecationWarning)
    finally:
        _debug_log_unlock ()

def debug_log_is_domain_enabled (domain):
    """Returns whether a certain domain is enabled in the debug log.
    If generating a log message is an expensive operation, you can first use
    this function to test whether the message needs to be logged at all.

    @domain: Domain to query.  Note that the "USER" domain is always enabled.

    Return value: True if the @domain is enabled for logging, False otherwise."""

    global _debug_log_log

    if type (domain) != str:
        raise TypeError ("domain must be a string")

    _debug_log_lock ()
    try:
        return _debug_log_log.is_domain_enabled (domain)
    finally:
        _debug_log_unlock ()

def debug_log_dump_as_list (config_filename):
    """Returns a list with the contents of the debug log, ready to be sent to
    a file.  This list contains both the milestones and the actual ring buffer
    used for logging.

    @config_filename: The generated list has instructions on how to re-create the
    debug log's configuration for a future run.  This string specifies the
    name of the file in which that configuration should be specified; the
    returned log will have instructions like "This configuration for the debug log
    can be re-created by putting the following in @config_filename".

    Return value: a list with the contents of the debug log, with one string item
    per message."""

    global _debug_log_log

    if type (config_filename) != str:
        raise TypeError ("config_filename must be a string")

    _debug_log_lock ()
    try:
        list = []
        _debug_log_log.dump_to_list (list, config_filename)
        return list
    finally:
        _debug_log_unlock ()

def debug_log_dump_to_file (config_filename, file):
    """Dumps the debug log to a file.

    @config_filename: See the documentation for debug_log_dump_as_list() to
    see how this argument is used.
    @file: open file object in which to dump the log."""

    list = debug_log_dump_as_list (config_filename)
    file.writelines (list)

def debug_log_dump_configuration (file):
    """Dumps the current configuration to the specified file object.

    @file: File object, already open for writing."""

    _debug_log_lock ()
    try:
        _debug_log_log.dump_configuration (file)
    finally:
        _debug_log_unlock ()

def debug_log_dump_to_dated_file (config_filename):
    """Dumps the debug log to a unique file, convenient for reading by the user.

    @config_filename: See the documentation for debug_log_dump_as_list() to
    see how this argument is used.

    Return value: string with the name of the generated file."""

    t = time.localtime ()

    basename = ("sabayon-debug-log-%s-%04d-%02d-%02d-%02d-%02d-%02d.txt" %
                (os.getpid (),
                 t.tm_year,
                 t.tm_mon,
                 t.tm_mday,
                 t.tm_hour,
                 t.tm_min,
                 t.tm_sec))

    name = os.path.join (util.get_home_dir (), basename)

    file = open (name, "w")
    debug_log_dump_configuration (file)
    file.close ()

    return name
