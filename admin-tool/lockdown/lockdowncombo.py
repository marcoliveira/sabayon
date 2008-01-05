#
# Copyright (C) 2006 Novell, Inc.
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
import re

import globalvar
import lockdownbutton

class PessulusLockdownCombo:
    def __init__ (self, key, combo, type, value_list):
        self.key = key
        self.combo = combo
        self.type = type
        self.value_list = value_list;
        self.lockdownbutton = None

    def attach (combo, button, key, type, value_list):
        lockdown = PessulusLockdownCombo (key, combo, type, value_list)
        lockdown.lockdownbutton = lockdownbutton.PessulusLockdownButton.new_with_widget (button)
        # FIXME: connect to toggled ...
        lockdown.__connect_and_update ()
        return lockdown
    attach = staticmethod (attach)

    def __connect_and_update (self):
        self.lockdownbutton.connect ("toggled",
                                     self.__on_lockdownbutton_toggled)

        self.combo.connect ("changed", self.__on_combo_changed)
        self.combo.connect ("destroy", self.__on_destroyed)

        self.notify_id = globalvar.applier.notify_add (self.key,
                                                       self.__on_notified)
        self.update_state()

    def update_state(self):
        if self.isInt():
            (val, mandatory) = globalvar.applier.get_int (self.key)
            if val == None:
                val = "<not-in-list>"
            else:
                val = str (val)
        else:
            (val, mandatory) = globalvar.applier.get_string (self.key)
        
        index = 0
        for i in range (len(self.value_list)):
            if self.value_list[i] == val:
                index = i + 1
                break

        if self.combo.get_property ("active") != index:
            self.combo.set_property ("active", index)
            
        self.combo.set_sensitive (globalvar.applier.key_is_writable (self.key))
        if mandatory != self.lockdownbutton.get ():
            self.lockdownbutton.set (mandatory)

    def __on_notified(self, data):
        self.update_state()
        
    def getValue(self):
        idx = self.combo.get_property("active")
        if (idx < 1 or idx > len(self.value_list)):
            val = None
        else:
            val = self.value_list [idx - 1]
        return val
        
    def isUnset(self):
        if self.getValue() == None or self.getValue() == "":
            return True
        else:
            return False
        
    def isInt(self):
        return self.type == "int"

    def __do_change(self):
        if self.isUnset():
# FIXME: we should really use a 'tri-state' scheme & 'unset' the key            
            return
        if globalvar.applier and globalvar.applier.key_is_writable (self.key):
            if self.isInt():
                globalvar.applier.set_int (self.key, int(self.getValue()),
                                           self.lockdownbutton.get ())
            else:
                globalvar.applier.set_string (self.key, self.getValue(),
                                              self.lockdownbutton.get ())

    def __on_combo_changed (self, data):
        self.__do_change()

    def __on_lockdownbutton_toggled (self, lockdownbutton, mandatory):
        self.__do_change ()

    def __on_destroyed (self, combobox):
        if self.notify_id:
            if globalvar.applier:
                globalvar.applier.notify_remove (self.notify_id)
            self.notify_id = None
