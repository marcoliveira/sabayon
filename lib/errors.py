_have_recoverable_error = False

def errors_have_recoverable_error ():
    return _have_recoverable_error

def errors_log_recoverable_exception (domain, msg):
    _have_recoverable_error = True
    debug_log (True, domain, "Got recoverable error: %s" % msg)
    debug_log_current_exception (domain)
