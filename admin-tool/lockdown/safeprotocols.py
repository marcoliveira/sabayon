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

import gconf
import gtk

try:
    set
except:
    from sets import Set as set

import globalvar
import simpleeditabletreeview

# Note that the idea is to only have one toggle to set/unset mandatory settings
# for this key and the disable_unsafe_protocols key.

class PessulusSafeProtocols:
    def __init__ (self, lockdownbutton, treeview, addbutton, editbutton, removebutton):
        self.notify_id = None
        self.key = "/apps/epiphany/lockdown/additional_safe_protocols"
        self.safe_protocols = None
        self.sensitive = True

        self.lockdownbutton = lockdownbutton
        self.lockdownbutton.connect ("toggled",
                                     self.__on_lockdownbutton_toggled)

        treeview.connect ("destroy", self.__on_destroyed)
        self.simpleeditabletreeview = simpleeditabletreeview.PessulusSimpleEditableTreeview (treeview, addbutton, editbutton, removebutton)
        self.simpleeditabletreeview.connect ("changed",
                                             self.__on_treeview_changed)

        (list, mandatory) = globalvar.applier.get_list (self.key,
                                                        gconf.VALUE_STRING)
        self.safe_protocols = set (list)
        self.__update_simpleeditabletreeview ()
        self.lockdownbutton.set (mandatory)
        self.notify_id = globalvar.applier.notify_add (self.key,
                                                       self.__on_notified)

    def set_sensitive (self, sensitive):
        self.sensitive = sensitive
        self.__update_sensitivity ()

    def __on_notified (self, data):
        (list, mandatory) = globalvar.applier.get_list (self.key,
                                                        gconf.VALUE_STRING)
        gconf_set = set (list)
        if gconf_set != self.safe_protocols:
            self.safe_protocols = gconf_set
            self.__update_simpleeditabletreeview ()
        if mandatory != self.lockdownbutton.get ():
            self.lockdownbutton.set (mandatory)

    def __on_lockdownbutton_toggled (self, lockdownbutton, mandatory):
        globalvar.applier.set_list (self.key, gconf.VALUE_STRING,
                                    list (self.safe_protocols),
                                    mandatory)

    def __on_treeview_changed (self, simpleeditabletreeview, new_set):
        if new_set != self.safe_protocols:
            self.safe_protocols = new_set.copy ()
            globalvar.applier.set_list (self.key, gconf.VALUE_STRING,
                                        list (self.safe_protocols),
                                        self.lockdownbutton.get ())

    def __update_sensitivity (self):
        if globalvar.applier:
            sensitive = self.sensitive and globalvar.applier.key_is_writable (self.key)
        else:
            sensitive = self.sensitive

        self.simpleeditabletreeview.set_sensitive (sensitive)

    def __update_simpleeditabletreeview (self):
        self.__update_sensitivity ()
        self.simpleeditabletreeview.update_set (self.safe_protocols)

    def __on_destroyed (self, treeview):
        if self.notify_id:
            if globalvar.applier:
                globalvar.applier.notify_remove (self.notify_id)
            self.notify_id = None
