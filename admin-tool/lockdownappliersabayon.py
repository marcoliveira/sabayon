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

import gconf
import util
import sessionwindow

from sabayon.lockdown import lockdownapplier

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class LockdownMonitor:
    def __init__ (self, key, handler, data):
        self.gconf_id = None
        self.key = key
        self.handler = handler
        self.data = data

class LockdownApplierSabayon (lockdownapplier.PessulusLockdownApplier):
    def __init__ (self, profile, changes_model):
        self.changes_model = changes_model
        self.source = profile.get_source ("GConf")
        self.client = gconf.client_get_default ()
        self.monitored_keys = {}

        self.changes_model.connect ("changed", self.__changes_model_changed)

    def __changes_model_changed (self, model, change):
        if change == None or change.get_source () != self.source:
            return
        key = change.get_id ()
        if self.monitored_keys.has_key (key):
            for monitor in self.monitored_keys[key]:
                monitor.handler (monitor.data)

    def supports_mandatory_settings (self):
        return True

    def get_schema (self, key):
        return self.client.get_schema (key)

    def __is_mandatory (self, key):
        iter = self.changes_model.find (self.source, key)
        if iter:
            return self.changes_model[iter][sessionwindow.ProfileChangesModel.COLUMN_MANDATORY]
        
        return self.source.get_gconf_key_is_mandatory (key)
        
    def get_bool (self, key):
        iter = self.changes_model.find (self.source, key)
        if iter:
            change = self.changes_model[iter][sessionwindow.ProfileChangesModel.COLUMN_CHANGE]
            val = change.value.get_bool()
        else:
            val = self.client.get_bool (key)
        
        return (val, self.__is_mandatory (key))
            
    def set_bool (self, key, value, mandatory):
        return self.source.set_gconf_boolean (key, value, mandatory)

    def get_list (self, key, list_type):
        value = self.client.get_list (key, list_type)
        return (value, self.__is_mandatory (key))

    def set_list (self, key, list_type, value, mandatory):
        return self.source.set_gconf_list (key, list_type, value, mandatory)

    def key_is_writable (self, key):
        return True

    def notify_add (self, key, handler, data = None):
        monitor = LockdownMonitor (key, handler, data)

        def __gconf_notify_proxy (client, cnx_id, entry, monitor):
            monitor.handler (monitor.data)
        
        monitor.gconf_id = self.source.add_gconf_notify (key, __gconf_notify_proxy, monitor)
        
        if self.monitored_keys.has_key (key):
            monitors = self.monitored_keys[key]
        else:
            monitors = []
            self.monitored_keys[key] = monitors
        monitors.append(monitor)
            
        return monitor
        
    def notify_remove (self, monitor):
        self.source.remove_gconf_notify (monitor.gconf_id)
        monitors = self.monitored_keys[monitor.key]
        monitors.remove (monitor)

    # We always monitor all dirs anyway
    def add_dir (self, dir, preloadtype):
        pass
    def remove_dir (self, dir):
        pass
        
