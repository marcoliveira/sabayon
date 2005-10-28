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
import gconf
import util
import sessionwindow

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_ADMINTOOL, fmt % args)

class LockdownMonitor:
    def __init__ (self, key, handler, data):
        self.gconf_id = None
        self.key = key
        self.handler = handler
        self.data = data

class LockdownApplier:
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

    def is_mandatory (self, key):
        iter = self.changes_model.find (self.source, key)
        if iter:
            return self.changes_model[iter][sessionwindow.ProfileChangesModel.COLUMN_MANDATORY]
        
        return self.source.get_gconf_key_is_mandatory (key)
        
    def get_boolean (self, key):
        iter = self.changes_model.find (self.source, key)
        if iter:
            change = self.changes_model[iter][sessionwindow.ProfileChangesModel.COLUMN_CHANGE]
            return change.value.get_bool()
        
        return self.client.get_bool (key)
            
    def set_boolean (self, key, value, mandatory):
        return self.source.set_gconf_boolean (key, value, mandatory)

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
        self.remove_gconf_notify (monitor.gconf_id)
        monitors = self.monitored_keys[monitor.key]
        monitors.remove (monitor)

class LockdownWindow:
    def __init__ (self, profile_name, profile, changes_model, parent_window):
        self.profile_name = profile_name
        self.applier = LockdownApplier (profile, changes_model)

        self.key = "/apps/panel/global/locked_down"

        self.window = gtk.Window (gtk.WINDOW_TOPLEVEL)
        self.window.set_title (_("Lockdown of profile %s")%profile_name)
        self.window.set_icon_name ("sabayon")
        self.window.set_transient_for (parent_window)
        self.window.set_destroy_with_parent (True)
        self.window.set_default_size (480, 380)
        self.window.connect ("delete-event",
                             gtk.Widget.hide_on_delete)
        self.ignore_change = False

        main_vbox = gtk.VBox (False, 0)
        self.window.add (main_vbox)


        hbox = gtk.HBox (False, 0)
        main_vbox.pack_start (hbox, False, False, 0)
       
        self.checkbutton = gtk.CheckButton("Lock down panel")
        hbox.pack_start (self.checkbutton, False, False, 0)
        
        self.mandatory_checkbutton = gtk.CheckButton("Mandatory")
        hbox.pack_start (self.mandatory_checkbutton, False, False, 0)

        self.checkbutton.connect ("toggled", self.__send_change)
        self.mandatory_checkbutton.connect ("toggled", self.__send_change)

        self.__update ()
        self.applier.notify_add (self.key, self.__handle_change)
        
        self.window.show_all ()

    def __send_change (self, checkbutton):
        if not self.ignore_change:
            active = self.checkbutton.get_active ()
            mandatory = self.mandatory_checkbutton.get_active ()
            self.applier.set_boolean (self.key, active, mandatory)

    def __handle_change (self, data):
        self.__update ()

    def __update (self):
        self.ignore_change = True
        
        self.checkbutton.set_active (self.applier.get_boolean (self.key))
        self.mandatory_checkbutton.set_active (self.applier.is_mandatory (self.key))
        
        self.ignore_change = False
