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

import globalvar
import lockdownbutton

class PessulusLockdownCheckbutton:
    def __init__ (self, key):
        self.notify_id = None
        self.key = key

        self.lockdownbutton = None
        self.checkbutton = None
        self.hbox = None

    def new (key, label):
        lockdown = PessulusLockdownCheckbutton (key)

        lockdown.hbox = gtk.HBox ()
        lockdown.lockdownbutton = lockdownbutton.PessulusLockdownButton.new ()

        lockdown.checkbutton = gtk.CheckButton (label)
        lockdown.checkbutton.show ()

        lockdown.hbox.pack_start (lockdown.lockdownbutton.get_widget (),
                                  False, False)
        lockdown.hbox.pack_start (lockdown.checkbutton)
        lockdown.hbox.show ()

        lockdown.__connect_and_update ()
        return lockdown
    new = staticmethod (new)

    def new_with_widgets (key, button, checkbutton):
        lockdown = PessulusLockdownCheckbutton (key)

        lockdown.lockdownbutton = lockdownbutton.PessulusLockdownButton.new_with_widget (button)
        lockdown.checkbutton = checkbutton
        lockdown.hbox = lockdown.checkbutton.get_parent ()

        lockdown.__connect_and_update ()
        return lockdown
    new_with_widgets = staticmethod (new_with_widgets)

    def __connect_and_update (self):
        self.__update_toggle ()

        self.lockdownbutton.connect ("toggled",
                                     self.__on_lockdownbutton_toggled)

        self.checkbutton.connect ("toggled", self.__on_check_toggled)
        self.checkbutton.connect ("destroy", self.__on_destroyed)

        self.notify_id = globalvar.applier.notify_add (self.key,
                                                       self.__on_notified)
        self.__set_tooltip ()

    def get_widget (self):
        return self.hbox

    def get_lockdownbutton (self):
        return self.lockdownbutton

    def __set_tooltip (self):
        if not globalvar.applier:
            return

        try:
            schema = globalvar.applier.get_schema ("/schemas" + self.key)
            if schema:
                globalvar.tooltips.set_tip (self.checkbutton,
                                            schema.get_long_desc ())
        except gobject.GError:
            print >> sys.stderr, "Warning: Could not get schema for %s" % self.key

    def __update_toggle (self):
        (active, mandatory) = globalvar.applier.get_bool (self.key)

        self.lockdownbutton.set (mandatory)

        self.checkbutton.set_active (active)
        self.checkbutton.set_sensitive (globalvar.applier.key_is_writable (self.key))

    def __on_notified (self, data):
        (active, mandatory) = globalvar.applier.get_bool (self.key)
        if active != self.checkbutton.get_active () or mandatory != self.lockdownbutton.get ():
            self.__update_toggle ()

    def __on_lockdownbutton_toggled (self, lockdownbutton, mandatory):
        self.__do_change ()

    def __on_check_toggled (self, checkbutton):
        self.__do_change ()

    def __do_change (self):
        if globalvar.applier and globalvar.applier.key_is_writable (self.key):
            globalvar.applier.set_bool (self.key,
                                        self.checkbutton.get_active (),
                                        self.lockdownbutton.get ())

    def __on_destroyed (self, checkbutton):
        if self.notify_id:
            if globalvar.applier:
                globalvar.applier.notify_remove (self.notify_id)
            self.notify_id = None
