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
import gobject
import lockdownapplier

from config import *

def can_edit_mandatory ():
    try:
        engine = gconf.engine_get_for_address (GCONF_MANDATORY_SOURCE)
    except gobject.GError:
        return False

    if engine == None:
        return False

    try:
        #entry = engine.get_entry ("/apps/gconf-editor/can_edit_source",
        #                          None,
        #                          False)
        #gconf_engine_get_entry() is not wrapped. Ugly workaround:
        client = gconf.client_get_for_engine (engine)
        entry = client.get_entry ("/apps/gconf-editor/can_edit_source", "",
                                  False)
    except gobject.GError:
        return False

    if entry != None:
        return entry.get_is_writable ()

    return False

# We have this safe class to be able to use gconf methods even if we don't have
# any gconf access. In the future, we might have non-gconf sources, so it's
# important to keep the gconf applier working (by being effectively disabled),
# even when gconf is not working.
class SafeGConfClient:
    def __init__ (self):
        self.client = gconf.client_get_default ()

        try:
            self.client.get_bool ("/apps/gconf-editor/can_edit_source")
            self.can_use = True
        except gobject.GError:
            self.can_use = False

    def really_works (self):
        return self.can_use

    def get_schema (self, key):
        if not self.can_use:
            return None
        return self.client.get_schema (key)

    def get_bool (self, key):
        if not self.can_use:
            return False
        return self.client.get_bool (key)

    def set_bool (self, key, value):
        if not self.can_use:
            return
        self.client.set_bool (key, value)

    def get_list (self, key, list_type):
        if not self.can_use:
            return []
        return self.client.get_list (key, list_type)

    def set_list (self, key, list_type, value):
        if not self.can_use:
            return
        self.client.set_list (key, list_type, value)

    def key_is_writable (self, key):
        if not self.can_use:
            return False
        return self.client.key_is_writable (key)

    def notify_add (self, key, handler, data = None):
        if not self.can_use:
            return None
        return self.client.notify_add (key, handler, data)

    def notify_remove (self, monitor):
        if not self.can_use:
            return
        self.client.notify_remove (monitor)

    def add_dir (self, dir, preloadtype):
        if not self.can_use:
            return
        self.client.add_dir (dir, preloadtype)

    def remove_dir (self, dir):
        if not self.can_use:
            return
        self.client.remove_dir (dir)

class PessulusLockdownApplierGconf (lockdownapplier.PessulusLockdownApplier):
    def __init__ (self):
        self.can_edit_mandatory = can_edit_mandatory ()
        self.client_mandatory = None

        if (self.can_edit_mandatory):
            engine = gconf.engine_get_for_address (GCONF_MANDATORY_SOURCE)
            self.client_mandatory = gconf.client_get_for_engine (engine)

        self.client = SafeGConfClient ()

    def supports_normal_settings (self):
        return self.client.really_works ()

    def supports_mandatory_settings (self):
        return self.can_edit_mandatory

    def get_schema (self, key):
        return self.client.get_schema (key)

    def get_bool (self, key):
        value = None
        is_mandatory = False

        if self.supports_mandatory_settings ():
            entry = self.client_mandatory.get_without_default (key)
            if entry != None:
                is_mandatory = True
                value = entry.get_bool ()
            else:
                value = self.client.get_bool (key)
        else:
            value = self.client.get_bool (key)

        return (value, is_mandatory)

    def set_bool (self, key, value, mandatory):
        if mandatory:
            if self.supports_mandatory_settings ():
                self.client_mandatory.set_bool (key, value)
        else:
            if self.supports_mandatory_settings ():
                self.client_mandatory.unset (key)
            self.client.set_bool (key, value)

    def get_list (self, key, list_type):
        value = None
        is_mandatory = False

        if self.supports_mandatory_settings ():
            entry = self.client_mandatory.get_without_default (key)
            if entry != None:
                is_mandatory = True
                list = entry.get_list ()
                type = entry.get_list_type ()
                value = []
                for element in list:
                    if type == gconf.VALUE_STRING:
                        value.append (element.get_string ())
                    elif type == gconf.VALUE_BOOL:
                        value.append (element.get_bool ())
                    elif type == gconf.VALUE_INT:
                        value.append (element.get_int ())
                    elif type == gconf.VALUE_FLOAT:
                        value.append (element.get_float ())
            else:
                value = self.client.get_list (key, list_type)
        else:
            value = self.client.get_list (key, list_type)

        return (value, is_mandatory)

    def set_list (self, key, list_type, value, mandatory):
        if mandatory:
            if self.supports_mandatory_settings ():
                self.client_mandatory.set_list (key, list_type, value)
        else:
            if self.supports_mandatory_settings ():
                self.client_mandatory.unset (key)
            self.client.set_list (key, list_type, value)

    def key_is_writable (self, key):
        if self.supports_mandatory_settings ():
            return True

        return self.client.key_is_writable (key)

    def notify_add (self, key, handler, data = None):
        def __gconf_notify_proxy (client, cnx_id, entry, monitor):
            handler = monitor[0]
            user_data = monitor[1]
            handler (user_data)
            
        return self.client.notify_add (key, __gconf_notify_proxy,
                                       (handler, data))

    def notify_remove (self, monitor):
        self.client.notify_remove (monitor)

    def add_dir (self, dir, preloadtype):
        self.client.add_dir (dir, preloadtype)

    def remove_dir (self, dir):
        self.client.remove_dir (dir)
