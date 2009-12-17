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

import os
import bonobo
import gconf
import gtk

try:
    set
except:
    from sets import Set as set

import globalvar
import icons

# there's no wrapper for g_get_language_names (). Ugly workaround:
# Note that we don't handle locale alias...
def get_language_names ():
    if "LANGUAGE" in os.environ.keys () and os.environ["LANGUAGE"] != "":
        env_lang = os.environ["LANGUAGE"].split ()
    elif "LC_ALL" in os.environ.keys () and os.environ["LC_ALL"] != "":
        env_lang = os.environ["LC_ALL"].split ()
    elif "LC_MESSAGES" in os.environ.keys () and os.environ["LC_MESSAGES"] != "":
        env_lang = os.environ["LC_MESSAGES"].split ()
    elif "LANG" in os.environ.keys () and os.environ["LANG"] != "":
        env_lang = os.environ["LANG"].split ()
    else:
        env_lang = []

    env_lang.reverse ()
    languages = []

    for language in env_lang:
        start_pos = 0
        mask = 0
        uscore_pos = language.find ("_")
        if uscore_pos != -1:
            start_pos = uscore_pos
            mask += 1 << 2
        dot_pos = language.find (".", start_pos)
        if dot_pos != -1:
            start_pos = dot_pos
            mask += 1 << 0
        at_pos = language.find ("@", start_pos)
        if at_pos != -1:
            start_pos = at_pos
            mask += 1 << 1

        if uscore_pos != -1:
            lang = language[:uscore_pos]
        elif dot_pos != -1:
            lang = language[:dot_pos]
        elif at_pos != -1:
            lang = language[:at_pos]
        else:
            lang = language

        if uscore_pos != -1:
            if dot_pos != -1:
                territory = language[uscore_pos:dot_pos]
            elif at_pos != -1:
                territory = language[uscore_pos:at_pos]
            else:
                territory = language[uscore_pos:]
        else:
            territory = ""

        if dot_pos != -1:
            if at_pos != -1:
                codeset = language[dot_pos:at_pos]
            else:
                codeset = language[dot_pos:]
        else:
            codeset = ""

        if at_pos != -1:
            modifier = language[at_pos:]
        else:
            modifier = ""

        for i in range (mask + 1):
            if i & ~mask == 0:
                newlang = lang
                if (i & 1 << 2):
                    newlang += territory
                if (i & 1 << 0):
                    newlang += codeset
                if (i & 1 << 1):
                    newlang += modifier
                languages.insert (0, newlang)

    return languages

class PessulusDisabledApplets:
    (
        COLUMN_IID,
        COLUMN_NAME,
        COLUMN_ICON_NAME,
        COLUMN_DISABLED
    ) = range (4)

    def __init__ (self, treeview, lockdownbutton):
        self.notify_id = None
        self.key = "/apps/panel/global/disabled_applets"
        self.disabled_applets = None

        self.liststore = gtk.ListStore (str, str, str, bool)
        self.liststore.set_sort_column_id (self.COLUMN_NAME, gtk.SORT_ASCENDING)

        self.treeview = treeview
        self.treeview.get_selection ().set_mode (gtk.SELECTION_SINGLE)
        self.treeview.set_model (self.liststore)
        self.treeview.connect ("destroy", self.__on_destroyed)

        self.lockdownbutton = lockdownbutton
        self.lockdownbutton.connect ("toggled",
                                     self.__on_lockdownbutton_toggled)

        self.__fill_liststore ()
        self.__create_columns ()

        (list, mandatory) = globalvar.applier.get_list (self.key,
                                                        gconf.VALUE_STRING)
        self.disabled_applets = set (list)
        self.__update_toggles ()
        self.lockdownbutton.set (mandatory)
        self.notify_id = globalvar.applier.notify_add (self.key,
                                                       self.__on_notified)

    def __fill_liststore (self):
        applets = bonobo.activation.query ("has_all (repo_ids, ['IDL:Bonobo/Control:1.0', 'IDL:GNOME/Vertigo/PanelAppletShell:1.0'])")

        languages = get_language_names ()

        for applet in applets:
            name = None
            icon = None
            # Workaround: bonobo_server_info_prop_lookup () is not wrapped
            for prop in applet.props:
                bestname = -1
                if prop.name[:5] == "name-" and prop.name[5:] in languages:
                    if bestname > languages.index (prop.name[5:]) or bestname == -1:
                        name = prop.v.value_string
                        bestname = languages.index (prop.name[5:])
                elif prop.name == "name" and bestname == -1:
                    name = prop.v.value_string
                elif prop.name == "panel:icon":
                    icon = icons.fix_icon_name(prop.v.value_string)

            if name == None:
                name = applet.iid
            else:
                #FIXME needs to be translated
                name = name + " (" + applet.iid + ")"

            iter = self.liststore.append ()
            self.liststore.set (iter,
                                self.COLUMN_IID, applet.iid,
                                self.COLUMN_NAME, name,
                                self.COLUMN_ICON_NAME, icon)

    def __create_columns (self):
        column = gtk.TreeViewColumn ()
        self.treeview.append_column (column)
        
        cell = gtk.CellRendererToggle ()
        cell.connect ("toggled", self.__on_toggled)
        column.pack_start (cell, False)
        column.set_attributes (cell, active = self.COLUMN_DISABLED)

        column = gtk.TreeViewColumn ()
        column.set_spacing (6)
        self.treeview.append_column (column)

        cell = gtk.CellRendererPixbuf ()
        column.pack_start (cell, False)
        column.set_attributes (cell, icon_name = self.COLUMN_ICON_NAME)

        cell = gtk.CellRendererText ()
        column.pack_start (cell, True)
        column.set_attributes (cell, text = self.COLUMN_NAME)

    def __on_lockdownbutton_toggled (self, lockdownbutton, mandatory):
        globalvar.applier.set_list (self.key, gconf.VALUE_STRING,
                                    list (self.disabled_applets),
                                    mandatory)

    def __on_toggled (self, toggle, path):
        def toggle_value (model, iter, column):
            model[iter][column] = not model[iter][column]
            return model[iter][column]

        iter = self.liststore.get_iter (path)
        active = toggle_value (self.liststore, iter, self.COLUMN_DISABLED)

        iid = self.liststore[iter][self.COLUMN_IID]
        if active:
            if iid not in self.disabled_applets:
                self.disabled_applets.add (iid)
                globalvar.applier.set_list (self.key, gconf.VALUE_STRING,
                                            list (self.disabled_applets),
                                            self.lockdownbutton.get ())
        elif iid in self.disabled_applets:
            self.disabled_applets.remove (iid)
            globalvar.applier.set_list (self.key, gconf.VALUE_STRING,
                                        list (self.disabled_applets),
                                        self.lockdownbutton.get ())

    def __on_notified (self, data):
        (list, mandatory) = globalvar.applier.get_list (self.key,
                                                        gconf.VALUE_STRING)
        gconf_set = set (list)
        if gconf_set != self.disabled_applets:
            self.disabled_applets = gconf_set
            self.__update_toggles ()
        if mandatory != self.lockdownbutton.get ():
            self.lockdownbutton.set (mandatory)

    def __update_toggles (self):
        def update_toggle (model, path, iter, data):
            active = model[iter][self.COLUMN_IID] in data.disabled_applets
            if model[iter][self.COLUMN_DISABLED] != active:
                model[iter][self.COLUMN_DISABLED] = active

        self.liststore.foreach (update_toggle, self)
        self.treeview.set_sensitive (globalvar.applier.key_is_writable (self.key))

    def __on_destroyed (self, treeview):
        if self.notify_id:
            if globalvar.applier:
                globalvar.applier.notify_remove (self.notify_id)
            self.notify_id = None
