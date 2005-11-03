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

import sys
import util
import pygtk; pygtk.require("2.0")

if __name__ == "__main__":
    util.init_gettext ()
    
    def add_mod_dir ():
        sys.path.append ("sources")
    def remove_mod_dir ():
        sys.path.remove ("sources")
    
    unit_tests = [
        ( "storage",       None,                 None,        None ),
        ( "util",          None,                 None,        None ),
        ( "dirmonitor",    None,                 None,        None ),
        ( "filessource",   None,                 add_mod_dir, remove_mod_dir ),
        ( "gconfsource",   _("Ignore WARNINGs"), add_mod_dir, remove_mod_dir ),
        ( "paneldelegate", _("Ignore WARNINGs"), add_mod_dir, remove_mod_dir ),
        ( "mozillasource",   None,                 add_mod_dir, remove_mod_dir ),
        ( "userprofile",   None,                 None,        None ),
        ( "userdb",        None,                 None,        None ),
        ( "cache",         None,                 None,        None )
          ]
    
    if len (sys.argv) > 1:
        tests_to_run = sys.argv[1:]
    else:
        tests_to_run = []
        for test in unit_tests:
            tests_to_run.append (test[0])

    def run_unit_tests (module):
        cmd = ("import %s\n%s.run_unit_tests ()") % (module, module)
        exec (cmd)
    
    for (module, msg, pre_func, post_func) in unit_tests:
        if not module in tests_to_run:
            continue
        if not msg:
            print _("Running %s tests") % module
        else:
            print _("Running %s tests (%s)") % (module, msg)
        if pre_func:
            pre_func ()
        run_unit_tests (module)
        if post_func:
            post_func ()

    print _("Success!")
