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

if __name__ == "__main__":
    print "Running util tests"
    import util
    util.run_unit_tests ()
    
    print "Running dirmonitor tests"
    import dirmonitor
    dirmonitor.run_unit_tests ()
    
    sys.path.append ("storage-modules")
    
    print "Running filessource tests"
    import filessource
    filessource.run_unit_tests ()

    print "Running gconfsource tests (ignore WARNINGs)"
    import gconfsource
    gconfsource.run_unit_tests ()

    sys.path.remove ("storage-modules")
    
    print "Running userprofile tests"
    import userprofile
    userprofile.run_unit_tests ()

    print "Success!"
    
