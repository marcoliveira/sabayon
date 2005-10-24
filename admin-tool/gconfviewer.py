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

import pygtk; pygtk.require('2.0')
import gtk
import gconf

class GConfModel (gtk.TreeStore):
    (
        COLUMN_NAME,
        COLUMN_TYPE,
        COLUMN_VALUE
    ) = range (3)
        
    def __init__ (self, client):
        gtk.TreeStore.__init__ (self, str, str, str)

        self.client = client
        self.__append_dir_contents (None, "/")

    def __append_dir_contents (self, parent_iter, dir):
        subdirs = list (self.client.all_dirs (dir))
        subdirs.sort ()
        for subdir in subdirs:
            iter = self.append (parent_iter)
            self.set (iter,
                      self.COLUMN_NAME, subdir[subdir.rfind ("/") + 1:])
            self.__append_dir_contents (iter, subdir)

        entries = list (self.client.all_entries (dir))
        entries.sort (lambda a, b: cmp (a.key, b.key))
        for entry in entries:
            iter = self.append (parent_iter)
            self.set (iter,
                      self.COLUMN_NAME, entry.key[entry.key.rfind ("/") + 1:])
            if entry.value:
                self.set (iter,
                          self.COLUMN_TYPE,  self.__type_to_string (entry.value.type),
                          self.COLUMN_VALUE, entry.value.to_string ())
            else:
                self.set (iter,
                          self.COLUMN_TYPE,  _("<no type>"),
                          self.COLUMN_VALUE, _("<no value>"))

    def __type_to_string (self, type):
        if type == gconf.VALUE_STRING:
            return _("string")
        elif type == gconf.VALUE_INT:
            return _("integer")
        elif type == gconf.VALUE_FLOAT:
            return _("float")
        elif type == gconf.VALUE_BOOL:
            return _("boolean")
        elif type == gconf.VALUE_SCHEMA:
            return _("schema")
        elif type == gconf.VALUE_LIST:
            return _("list")
        elif type == gconf.VALUE_PAIR:
            return _("pair")
        else:
            return _("<no type>")

class GConfViewer (gtk.Window):
    def __init__ (self, xml_backend_dir, parent_window):
        gtk.Window.__init__ (self, gtk.WINDOW_TOPLEVEL)
        
        self.backend_address = "xml:readonly:" + xml_backend_dir
        self.engine = gconf.engine_get_for_address ("xml:readonly:" + xml_backend_dir)
        self.client = gconf.client_get_for_engine (self.engine)

        self.set_title (_("All Your Settings Are Belong To Us"))
        self.set_icon_name ("sabayon")
        self.set_transient_for (parent_window)
        self.set_destroy_with_parent (True)
        self.set_default_size (480, 380)

        self.scrolled = gtk.ScrolledWindow ()
        self.scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.set_shadow_type (gtk.SHADOW_IN)
        self.scrolled.show ()
        self.add (self.scrolled)

        self.__setup_treeview ()
    
    def __setup_treeview (self):
        self.gconf_model = GConfModel (self.client)

        self.treeview = gtk.TreeView (self.gconf_model)
        self.treeview.show ()
        self.scrolled.add (self.treeview)

        self.treeview.get_selection ().set_mode (gtk.SELECTION_NONE)
        self.treeview.set_headers_visible (True)

        c = gtk.TreeViewColumn (_("Name"),
                                gtk.CellRendererText (),
                                text = GConfModel.COLUMN_NAME)
        self.treeview.append_column (c)
        
        c = gtk.TreeViewColumn (_("Type"),
                                gtk.CellRendererText (),
                                text = GConfModel.COLUMN_TYPE)
        self.treeview.append_column (c)
        
        c = gtk.TreeViewColumn (_("Value"),
                                gtk.CellRendererText (),
                                text = GConfModel.COLUMN_VALUE)
        self.treeview.append_column (c)

        self.treeview.expand_all ()
