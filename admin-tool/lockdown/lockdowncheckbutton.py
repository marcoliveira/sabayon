#!/usr/bin/env python

# vim: set ts=4 sw=4 et:

#
# Copyright (C) 2005 Vincent Untz <vuntz@gnome.org>
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301, USA
#

import gobject
import gtk
import gconf
import sys

def load_image (name):
    image = gtk.Image ()
    image.set_from_icon_name (name, gtk.ICON_SIZE_MENU)
    image.show ()
    return image

class PessulusLockdownCheckbutton:
    def __init__ (self, applier, key):
        self.notify_id = None
        self.applier = applier
        self.key = key
        self.locked = False

        self.button = None
        self.checkbutton = None
        self.hbox = None

        self.locked_image = load_image ("stock_lock")
        self.unlocked_image = load_image ("stock_lock-open")

        self.tooltips = gtk.Tooltips ()

    def new (applier, key, label):
        lockdown = PessulusLockdownCheckbutton (applier, key)

        lockdown.hbox = gtk.HBox ()
        lockdown.button = gtk.Button ()

        lockdown.checkbutton = gtk.CheckButton (label)
        lockdown.checkbutton.show ()

        lockdown.hbox.pack_start (lockdown.button, False, False)
        lockdown.hbox.pack_start (lockdown.checkbutton)
        lockdown.hbox.show ()

        lockdown.__connect_and_update ()
        return lockdown
    new = staticmethod (new)

    def new_with_widgets (applier, key, button, checkbutton):
        lockdown = PessulusLockdownCheckbutton (applier, key)

        lockdown.button = button
        lockdown.checkbutton = checkbutton
        lockdown.hbox = lockdown.button.get_parent ()

        button.remove (button.get_child ())

        lockdown.__connect_and_update ()
        return lockdown
    new_with_widgets = staticmethod (new_with_widgets)

    def __connect_and_update (self):
        self.button.set_relief (gtk.RELIEF_NONE)
        self.button.connect ("clicked", self.__on_button_clicked)

        self.button.add (self.unlocked_image)

        if self.applier.supports_mandatory_settings ():
            self.button.show ()
        else:
            self.button.hide ()

        self.checkbutton.connect ("toggled", self.__on_check_toggled)
        self.checkbutton.connect ("destroy", self.__on_destroyed)

        self.__update_toggle ()
        self.notify_id = self.applier.notify_add (self.key, self.__on_notified)
        self.set_tooltip ()

    def get_hbox (self):
        return self.hbox

    def set_tooltip (self):
        if not self.applier:
            return

        try:
            schema = self.applier.get_schema ("/schemas" + self.key)
            if schema:
                self.tooltips.set_tip (self.checkbutton, schema.get_long_desc ())
        except gobject.GError:
            print >> sys.stderr, "Warning: Could not get schema for %s" % self.key

    def __update_toggle (self):
        (active, mandatory) = self.applier.get_bool (self.key)

        self.locked = mandatory
        self.__set_button_icon ()

        self.checkbutton.set_active (active)
        self.checkbutton.set_sensitive (self.applier.key_is_writable (self.key))

    def __set_button_icon (self):
        if self.locked:
            newimage = self.locked_image
        else:
            newimage = self.unlocked_image

        if self.button.get_child () != newimage:
            self.button.remove (self.button.get_child ())
            self.button.add (newimage)

    def __on_notified (self, data):
        (active, mandatory) = self.applier.get_bool (self.key)
        if active != self.checkbutton.get_active () or mandatory != self.locked:
            self.__update_toggle ()

    def __on_button_clicked (self, button):
        self.locked = not self.locked

        self.__set_button_icon ()

        if self.applier and self.applier.key_is_writable (self.key):
            self.applier.set_bool (self.key, self.checkbutton.get_active (),
                                   self.locked)

    def __on_check_toggled (self, checkbutton):
        if self.applier and self.applier.key_is_writable (self.key):
            self.applier.set_bool (self.key, self.checkbutton.get_active (),
                                   self.locked)

    def __on_destroyed (self, checkbutton):
        if self.notify_id:
            if self.applier:
                self.applier.notify_remove (self.notify_id)
            self.notify_id = None

        if self.applier:
            self.applier = None
