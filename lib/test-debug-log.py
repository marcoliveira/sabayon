import debuglog
import sys

debuglog.debug_log_load_configuration ("test-debug-log.conf")

for i in range (1000):
    is_milestone = (i % 10 == 0)

    m = i % 3
    if m == 0:
        domain = "foo"
    elif m == 1:
        domain = "bar"
    elif m == 2:
        domain = debuglog.DEBUG_LOG_DOMAIN_USER

    debuglog.debug_log (is_milestone, domain, "%s" % i)
    print "logged %s" % i

debuglog.debug_log_dump_to_file ("test-debug-log.conf",sys.stderr)
