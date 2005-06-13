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

import gtk
import util
import protosession
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class SessionWindow:
    def __init__ (self, username, profile_name):
        self.username     = username
        self.profile_name = profile_name
        
        self.session = protosession.ProtoSession (username, self.profile_name)

        screen = gtk.gdk.screen_get_default ()
        width  = (screen.get_width ()  * 3) / 4
        height = (screen.get_height () * 3) / 4

        dprint ("Creating %dx%d session window" % (width, height))
        
        self.window = gtk.Window ()
        self.window.connect ("destroy", gtk.main_quit)
        self.window.set_default_size (width, height)
        
        self.mapped_handler_id = self.window.connect ("map-event", self.__window_mapped)
        
        self.window.show ()

    def __window_mapped (self, window, event):
        dprint ("Session window mapped; starting prototype session")
        self.window.disconnect (self.mapped_handler_id)
        self.mapped_handler_id = 0
        self.session.connect ("finished", self.__session_finished)
        self.session.start (str (self.window.window.xid))
        return False

    def __session_finished (self, session):
        self.window.destroy ()
