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

import gobject
import gtk
import gtk.gdk
import util
import userprofile
import debuglog
import errors

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL, fmt % args)

class PixbufToggleRenderer (gtk.CellRendererPixbuf):
    __gsignals__ = {
        "toggled" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (str, ))
        }
    
    def __init__ (self):
        gtk.CellRendererPixbuf.__init__ (self)
        self.set_property ("mode", gtk.CELL_RENDERER_MODE_ACTIVATABLE)

    def do_activate (self, event, widget, path, background_area, cell_area, flags):
        self.emit ("toggled", path)
        
gobject.type_register (PixbufToggleRenderer)

class ChangesWindow:
    def __init__ (self, changes_model, profile_name, parent_window):
        self.changes_model = changes_model
        
        self.window = gtk.Window ()
        self.window.set_transient_for (parent_window)
        self.window.set_title (_("Changes in profile %s")%profile_name)
        self.window.set_icon_name ("sabayon")

        (width, height) = parent_window.get_size ()
        width  = width  * 3 / 4
        height = height * 3 / 4
        self.window.set_default_size (width, height)

        self.scrolled = gtk.ScrolledWindow ()
        self.scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.window.add (self.scrolled)
        self.scrolled.show ()

        self.treeview = gtk.TreeView ()
        self.scrolled.add (self.treeview)
        self.treeview.show ()

        self.__setup_treeview ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_ADMIN_TOOL)
    def __mandatory_data_method (self, column, cell, model, iter):
        ignore = self.changes_model.get_value (iter,
                                               self.changes_model.COLUMN_IGNORE)
        cell.set_property ("sensitive", not ignore)
        if ignore:
            cell.set_property ("mode", gtk.CELL_RENDERER_MODE_INERT)
        else:
            cell.set_property ("mode", gtk.CELL_RENDERER_MODE_ACTIVATABLE)
            
    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __on_ignore_toggled (self, toggle, path):
        iter = self.changes_model.get_iter_from_string (path)
        ignore = self.changes_model.get_value (iter, self.changes_model.COLUMN_IGNORE)
        description = self.changes_model.get_value (iter, self.changes_model.COLUMN_DESCRIPTION)

        ignore = not ignore
        debuglog.uprint ('ChangesWindow: setting "%s" to ignore=%s', description, ignore)

        self.changes_model.set (iter, self.changes_model.COLUMN_IGNORE, ignore)
    
    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __on_mandatory_toggled (self, toggle, path):
        iter = self.changes_model.get_iter_from_string (path)
        mandatory = self.changes_model.get_value (iter, self.changes_model.COLUMN_MANDATORY)
        description = self.changes_model.get_value (iter, self.changes_model.COLUMN_DESCRIPTION)
        
        mandatory = not mandatory
        debuglog.uprint ('ChangesWindow: setting "%s" to mandatory=%s', description, mandatory)
        
        if mandatory:
            lock_pixbuf = self.changes_model.locked_pixbuf
        else:
            lock_pixbuf = self.changes_model.unlocked_pixbuf

        self.changes_model.set (iter, self.changes_model.COLUMN_MANDATORY,   mandatory)
        self.changes_model.set (iter, self.changes_model.COLUMN_LOCK_PIXBUF, lock_pixbuf);
        self.changes_model.emit ("changed", self.changes_model.get_value (iter, self.changes_model.COLUMN_CHANGE))
    
    def __setup_treeview (self):
        self.treeview.set_model (self.changes_model)
        
        cell = gtk.CellRendererToggle ()
        cell.connect ("toggled", self.__on_ignore_toggled)
        column = gtk.TreeViewColumn (_("Ignore"),
                                     cell,
                                     active = self.changes_model.COLUMN_IGNORE)
        self.treeview.append_column (column)
            
        cell = PixbufToggleRenderer ()
        cell.connect ("toggled", self.__on_mandatory_toggled)
        column = gtk.TreeViewColumn (_("Lock"),
                                     cell,
                                     pixbuf = self.changes_model.COLUMN_LOCK_PIXBUF)
        column.set_cell_data_func (cell, self.__mandatory_data_method)
        self.treeview.append_column (column)
        
        cell = gtk.CellRendererText ()
        column = gtk.TreeViewColumn (_("Description"),
                                     gtk.CellRendererText (),
                                     text = self.changes_model.COLUMN_DESCRIPTION)
        self.treeview.append_column (column)
        
        self.treeview.get_selection ().set_mode (gtk.SELECTION_SINGLE)
