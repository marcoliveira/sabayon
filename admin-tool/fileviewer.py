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

class FileViewer (gtk.Window):
    def __init__ (self, path, description, parent_window):
        gtk.Window.__init__ (self, gtk.WINDOW_TOPLEVEL)

        self.path = path
        
        self.set_title (_("Profile file: %s")%description)
        self.set_icon_name ("sabayon")
        self.set_transient_for (parent_window)
        self.set_destroy_with_parent (True)
        self.set_default_size (480, 380)

        self.scrolled = gtk.ScrolledWindow ()
        self.scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.set_shadow_type (gtk.SHADOW_IN)
        self.scrolled.show ()
        self.add (self.scrolled)

        self.__setup_textview ()
    
    def __setup_textview (self):
        self.textview = gtk.TextView ()
        self.textview.set_editable (False)
        self.textview.set_wrap_mode (gtk.WRAP_WORD)
        self.textview.show()
        
        self.scrolled.add (self.textview)

        buffer = self.textview.get_buffer ()
        buffer.set_text (file (self.path).read ())
