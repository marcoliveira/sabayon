import sys
import util
import debuglog

class RecoverableApplyErrorException (Exception):
    pass

class FatalApplyErrorException (Exception):
    pass

_have_recoverable_error = False

def errors_have_recoverable_error ():
    """Used to see if there was a recoverable error reported with
    errors_log_recoverable_exception() or errors_log_recoverable_error().

    Return value: True if errors_log_recoverable_exception() has been called;
    False otherwise."""

    return _have_recoverable_error

def errors_log_recoverable_error (domain, msg):
    """Records the presence of a recoverable error to the debug log
    (see debuglog).  This condition can be checked later with
    errors_have_recoverable_error().

    @domain: name of debug log domain
    @msg: message to print to the debug log""" 

    _have_recoverable_error = True
    debug_log (True, domain, "Got recoverable error: %s" % msg)

def errors_log_recoverable_exception (domain, msg):
    """Reports the current exception to the debug log (see debuglog), and records
    the presence of a recoverable error.  This condition can be checked later
    with errors_have_recoverable_error().

    @domain: name of debug log domain
    @msg: message to print to the debug log in addition to the current exception""" 

    errors_log_recoverable_error (domain, msg)
    debug_log_current_exception (domain)

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
