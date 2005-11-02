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

import simpleeditabletreeview

class PessulusSafeProtocols:
    def __init__ (self, applier, treeview, addbutton, editbutton, removebutton):
        self.notify_id = None
        self.applier = applier
        self.key = "/apps/epiphany/lockdown/additional_safe_protocols"
        self.safe_protocols = None
        self.sensitive = True

        treeview.connect ("destroy", self.__on_destroyed)
        self.simpleeditabletreeview = simpleeditabletreeview.PessulusSimpleEditableTreeview (treeview, addbutton, editbutton, removebutton)
        self.simpleeditabletreeview.connect ("changed",
                                             self.__on_treeview_changed)

        (list, mandatory) = self.applier.get_list (self.key, gconf.VALUE_STRING)
        self.safe_protocols = set (list)
        self.__update_simpleeditabletreeview ()
        self.notify_id = self.applier.notify_add (self.key, self.__on_notified)

    def set_sensitive (self, sensitive):
        self.sensitive = sensitive
        self.__update_sensitivity ()

    def __on_notified (self, data):
        (list, mandatory) = self.applier.get_list (self.key, gconf.VALUE_STRING)
        gconf_set = set (list)
        if gconf_set != self.safe_protocols:
            self.safe_protocols = gconf_set
            self.__update_simpleeditabletreeview ()

    def __on_treeview_changed (self, simpleeditabletreeview, new_set):
        if new_set != self.safe_protocols:
            self.safe_protocols = new_set.copy ()
    #FIXME
            self.applier.set_list (self.key, gconf.VALUE_STRING,
                                   list (self.safe_protocols), False)

    def __update_sensitivity (self):
        if self.applier:
            sensitive = self.sensitive and self.applier.key_is_writable (self.key)
        else:
            sensitive = self.sensitive

        self.simpleeditabletreeview.set_sensitive (sensitive)

    def __update_simpleeditabletreeview (self):
        self.__update_sensitivity ()
        self.simpleeditabletreeview.update_set (self.safe_protocols)

    def __on_destroyed (self, treeview):
        if self.notify_id:
            if self.applier:
                self.applier.notify_remove (self.notify_id)
            self.notify_id = None

        if self.applier:
            self.applier = None
