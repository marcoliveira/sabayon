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
import sys

try:
    set
except:
    from sets import Set as set

class PessulusSimpleEditableTreeview (gobject.GObject):
    (
        COLUMN_EDITABLE,
    ) = range (1)

    __gsignals__ = {
        "changed" : ( gobject.SIGNAL_RUN_LAST, None, (gobject.TYPE_PYOBJECT,) )
    }

    def __init__ (self, treeview, addbutton, editbutton, removebutton, sort = True, strip_text = True):
        gobject.GObject.__init__(self)

        self.content_set = None
        self.selected_content = None
        self.new_edited_path = None
        self.editing = False
        self.sensitive = True
        self.strip_text = strip_text

        self.treeview = treeview
        self.addbutton = addbutton
        self.editbutton = editbutton
        self.removebutton = removebutton

        self.liststore = gtk.ListStore (str)
        self.treeview.set_model (self.liststore)
        if sort:
            self.liststore.set_sort_column_id (self.COLUMN_EDITABLE,
                                               gtk.SORT_ASCENDING)

        self.__create_columns ()

        self.addbutton.connect ("clicked", self.__on_add_button_clicked)
        self.editbutton.connect ("clicked", self.__on_edit_button_clicked)
        self.removebutton.connect ("clicked", self.__on_remove_button_clicked)

        treeselection = self.treeview.get_selection ()
        treeselection.set_mode (gtk.SELECTION_SINGLE)
        treeselection.connect ("changed", self.__on_treeselection_changed)

        self.__update_sensitivity ()

    def __create_columns (self):
        self.column = gtk.TreeViewColumn ()
        self.treeview.append_column (self.column)

        self.cell = gtk.CellRendererText ()
        self.column.pack_start (self.cell, True)
        self.column.set_attributes (self.cell, text = self.COLUMN_EDITABLE)

        self.cell.set_property("editable", True)
        self.cell.connect("edited", self.__on_cell_edited)
        # we want to know if we're editing or not
        self.cell.connect("editing-started", self.__on_cell_editing_started)
        # we need to connect to this signal since if we add a row
        # and don't edit it, it shouldn't be really added
        self.cell.connect("editing-canceled", self.__on_cell_editing_canceled)

    def __on_cell_edited (self, cell, path, new_text):
        self.editing = False
        self.__update_sensitivity ()

        new = False
        if self.new_edited_path:
            if self.new_edited_path != path:
                new = True
            else:
                print >> sys.stderr, "Warning: path should have been a new edited one in the treeview"
            self.new_edited_path = None

        if self.strip_text:
            text = new_text.strip ()
        else:
            text = new_text

        # don't accept new items that are ""
        if text == "" and new:
            del (self.liststore[path])
            return

        if new or self.liststore[path][self.COLUMN_EDITABLE] != text:
            # save the selected content so that it will be selected again
            # later
            self.selected_content = text

            if not new:
                self.content_set.remove (self.liststore[path][self.COLUMN_EDITABLE])
            if text != "":
                self.content_set.add (text)

            self.__update_model ()
            self.emit ("changed", self.content_set)

    def __on_cell_editing_started (self, cell, editable, path):
        self.editing = True
        self.__update_sensitivity ()

    def __on_cell_editing_canceled (self, cell):
        self.editing = False
        self.__update_sensitivity ()

        if self.new_edited_path:
            del (self.liststore[self.new_edited_path])
            self.new_edited_path = None

    def __on_add_button_clicked (self, button):
        # add a row and start editing it
        iter = self.liststore.append ()
        path = self.liststore.get_path (iter)
        self.treeview.set_cursor_on_cell (path, self.column, self.cell, True)
        self.new_edited_path = path

    def __on_edit_button_clicked (self, button):
        model, iter = self.treeview.get_selection ().get_selected ()

        # if nothing selected...
        if not iter:
            print >> sys.stderr, "Warning: ask for edition in treeview while nothing selected"
            return

        path = model.get_path (iter)
        self.treeview.set_cursor_on_cell (path, self.column, self.cell, True)

    def __on_remove_button_clicked (self, button):
        model, iter = self.treeview.get_selection ().get_selected ()

        # if nothing selected...
        if not iter:
            print >> sys.stderr, "Warning: ask for removal in treeview while nothing selected"
            return

        selected_value = model[iter][self.COLUMN_EDITABLE]

        # if selection should not be here...
        if selected_value not in self.content_set:
            print >> sys.stderr, "Warning: %s should not be in the treeview" % selected_value
            del (model[iter])
            return
        
        # try to find the future selection (after this item has been removed)
        # note that we can not save a path since the paths might change
        new_selected_iter = model.iter_next (iter)
        if not new_selected_iter:
            # there's no next item. This item was the last one. Select the
            # item that's before.
            children = model.iter_n_children (None)
            if children > 1:
                new_selected_iter = model.iter_nth_child (None, children - 2)
        if new_selected_iter:
            path = model.get_path (new_selected_iter)
            self.selected_content = model[path][self.COLUMN_EDITABLE]

        self.content_set.remove (selected_value)
        self.__update_model ()
        self.emit ("changed", self.content_set)

    def __on_treeselection_changed (self, treeselection):
        self.__update_sensitivity ()

    def __update_sensitivity (self):
        self.treeview.set_sensitive (self.sensitive)

        sensitive = self.sensitive and not self.editing
        self.addbutton.set_sensitive (sensitive)

        selected = self.treeview.get_selection ().count_selected_rows () > 0

        sensitive = self.sensitive and not self.editing and selected
        self.editbutton.set_sensitive (sensitive)

        sensitive = self.sensitive and selected
        self.removebutton.set_sensitive (sensitive)

    def __update_model (self):
        def select_if_should (model, path, iter, data):
            if self.selected_content == model[path][data.COLUMN_EDITABLE]:
                data.treeview.get_selection ().select_path (path)
                data.treeview.scroll_to_cell (path)
                return True

        self.liststore.clear ()

        for value in self.content_set:
            iter = self.liststore.append ()
            self.liststore.set (iter, self.COLUMN_EDITABLE, value)

        if self.selected_content:
            self.liststore.foreach (select_if_should, self)
            self.selected_content = None

        self.__update_sensitivity ()

    def set_sensitive (self, sensitive):
        self.sensitive = sensitive
        self.__update_sensitivity ()

    def update_set (self, set):
        if set == self.content_set:
            return

        model, iter = self.treeview.get_selection ().get_selected ()
        if iter:
            # save the selected content so that it will be selected again
            # later
            self.selected_content = model[iter][self.COLUMN_EDITABLE]

        self.content_set = set.copy ()
        self.__update_model ()

if gtk.pygtk_version < (2, 8, 0):
    gobject.type_register (PessulusSimpleEditableTreeview)
