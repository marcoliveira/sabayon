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
import sessionwidget
from config import *

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class SessionWindow:
    def __init__ (self, username, profile_name):
        self.username     = username
        self.profile_name = profile_name
        
        self.session = protosession.ProtoSession (username, self.profile_name)

        self.window = gtk.Window ()
        self.window.set_title (_("All Your Settings Are Belong To Us"))
        self.window.set_icon_name ("sabayon")
        self.window.connect ("destroy", gtk.main_quit)

        screen = gtk.gdk.screen_get_default ()
        width  = (screen.get_width ()  * 3) / 4
        height = (screen.get_height () * 3) / 4

        dprint ("Creating %dx%d session wiget" % (width, height))
        
        self.session_widget = sessionwidget.SessionWidget (width, height)
        self.window.add (self.session_widget)
        self.mapped_handler_id = self.session_widget.connect ("map-event", self.__session_mapped)
        self.session_widget.show ()
        
        self.window.show ()

    def __session_mapped (self, session_widget, event):
        dprint ("Session widget mapped; starting prototype session")
        self.session_widget.disconnect (self.mapped_handler_id)
        self.mapped_handler_id = 0
        self.session.connect ("finished", self.__session_finished)
        self.session.start (str (self.session_widget.session_window.xid))
        return False

    def __session_finished (self, session):
        self.window.destroy ()
