import sys
import gtk
import util
import debuglog

class RecoverableApplyErrorException (Exception):
    pass

class FatalApplyErrorException (Exception):
    pass

_have_recoverable_error = False

_have_fatal_error = False

def errors_have_recoverable_error ():
    """Used to see if there was a recoverable error reported with
    errors_log_recoverable_exception() or errors_log_recoverable_error().

    Return value: True if errors_log_recoverable_exception() has been called;
    False otherwise."""

    global _have_recoverable_error
    return _have_recoverable_error

def errors_log_recoverable_error (domain, msg):
    """Records the presence of a recoverable error to the debug log
    (see debuglog).  This condition can be checked later with
    errors_have_recoverable_error().

    @domain: name of debug log domain
    @msg: message to print to the debug log""" 

    global _have_recoverable_error
    _have_recoverable_error = True
    debuglog.debug_log (True, domain, "Got recoverable error: %s" % msg)

def errors_have_fatal_error ():
    """Used to see if there was a fatal error reported with
    errors_log_fatal_error().

    Return value: True if errors_log_fatal_error() has been called;
    False otherwise."""

    global _have_fatal_error
    return _have_fatal_error

def errors_log_fatal_error (domain, msg):
    """Records the presence of a fatal error to the debug log
    (see debuglog).  This condition can be checked later with
    errors_have_fatal_error().

    @domain: name of debug log domain
    @msg: message to print to the debug log""" 

    global _have_fatal_error
    _have_fatal_error = True
    debuglog.debug_log (True, domain, "Got fatal error: %s" % msg)

def errors_log_recoverable_exception (domain, msg):
    """Reports the current exception to the debug log (see debuglog), and records
    the presence of a recoverable error.  This condition can be checked later
    with errors_have_recoverable_error().

    @domain: name of debug log domain
    @msg: message to print to the debug log in addition to the current exception""" 

    errors_log_recoverable_error (domain, msg)
    debuglog.debug_log_current_exception (domain)

def errors_exit_helper_normally (log_config_filename):
    """Used only from helper programs for Sabayon.  First, this dumps the debug log
    to stderr.  Then, it exits the program with exit code utils.EXIT_CODE_NORMAL
    if there were no recoverable errors during its execution, or with
    utils.EXIT_CODE_RECOVERABLE if there were recoverable errors.

    @log_config_filename: File to mention in the debug log as the source for its configuration

    Return value: this function does not return, as it exits the program."""

    # We are a helper program, so we *always* dump the log, since
    # the caller program will know what to do with it:
    # "sabayon-session" will pass it on to the parent "sabayon";
    # xinitrc will log it to ~/.xsession-errors, etc.
    debuglog.debug_log_dump_to_file (log_config_filename, sys.stderr)

    if errors_have_recoverable_error ():
        sys.exit (util.EXIT_CODE_RECOVERABLE)
    else:
        sys.exit (util.EXIT_CODE_NORMAL)

def errors_exit_with_fatal_exception (domain, log_config_filename):
    """Exits the program when a fatal exception has occurred.  First, this logs the
    current exception to the debug log.  Then, it dumps the debug log to stderr
    and exits the program with exit code util.EXIT_CODE_FATAL.

    @domain: name of debug log domain
    @log_config_filename:  File to mention in the debug log as the source for its configuration

    Return value: this function does not return, as it exits the program."""

    debuglog.debug_log (True, domain, "Fatal exception!  Exiting abnormally.")
    debuglog.debug_log_current_exception (domain)
    debuglog.debug_log_dump_to_file (log_config_filename, sys.stderr)
    sys.exit (util.EXIT_CODE_FATAL)

def checked_callback (domain):
    """Used as a function decorator.  You should prefix *all* your callbacks with this decorator:

    @checked_callback ("domain")
    def my_callback (...):
        ...

    If an uncaught exception happens in the callback, the decorator will catch the exception,
    call errors.errors_log_fatal_error() to flag the presence of a fatal error, and it will
    also exit the main loop.  In turn, the main loop is expected to have this form:

        gtk.main ()
        if errors.errors_have_fatal_error ():
            print "a fatal error occurred" # or anything else you want to do""" 

    def catch_exceptions (func):
        def wrapper (*args, **kwargs):
            try:
                return func (*args, **kwargs)
            except:
                errors_log_fatal_error (domain, "Fatal exception in callback; exiting main loop")
                debuglog.debug_log_current_exception (domain)
                gtk.main_quit ()

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return catch_exceptions
