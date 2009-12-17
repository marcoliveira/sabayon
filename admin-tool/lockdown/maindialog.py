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

import os.path
import gconf
import gettext
import gobject
import gtk

from xml.sax.saxutils import escape as escape_pango

from config import *

import disabledapplets
import lockdownbutton
import lockdowncheckbutton
import globalvar
import safeprotocols

gettext.install (PACKAGE, LOCALEDIR)

pages = (
    ( _('General'), "gnome-logo-icon-transparent", "vbox7" ),
    ( _('Panel'), "gnome-panel", "vbox12" ),
    ( _('Epiphany Web Browser'), "web-browser", "vboxEpiphany" ),
    ( _('GNOME Screensaver'), "preferences-desktop-screensaver", "vbox15" )
)

gconfdirs = [
"/desktop/gnome/lockdown",
"/apps/epiphany/lockdown",
"/apps/panel/global"
]

lockdownbuttons = (
    ( "/desktop/gnome/lockdown/disable_command_line", _("Disable _command line"), "vbox7" ),
    ( "/desktop/gnome/lockdown/disable_printing", _("Disable _printing"), "vbox7" ),
    ( "/desktop/gnome/lockdown/disable_print_setup", _("Disable print _setup"), "vbox7" ),
    ( "/desktop/gnome/lockdown/disable_save_to_disk", _("Disable save to _disk"), "vbox7" ),

    ( "/apps/panel/global/locked_down", _("_Lock down the panels"), "vbox8" ),
    ( "/apps/panel/global/disable_force_quit", _("Disable force _quit"), "vbox8" ),
    ( "/apps/panel/global/disable_log_out", _("Disable log _out"), "vbox8" ),

    ( "/apps/epiphany/lockdown/disable_quit", _("Disable _quit"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_arbitrary_url", _("Disable _arbitrary URL"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_bookmark_editing", _("Disable _bookmark editing"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_history", _("Disable _history"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_javascript_chrome", _("Disable _javascript chrome"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_toolbar_editing", _("Disable _toolbar editing"), "vbox9" ),
    ( "/apps/epiphany/lockdown/fullscreen", _("Force _fullscreen mode"), "vbox9" ),
    ( "/apps/epiphany/lockdown/hide_menubar", _("Hide _menubar"), "vbox9" ),

    ( "/desktop/gnome/lockdown/disable_lock_screen", _("Disable lock _screen"), "vbox15" ),
    ( "/apps/gnome-screensaver/lock_enabled", _("_Lock on activation"), "vbox15" ),
    ( "/apps/gnome-screensaver/logout_enabled", _("Allow log _out"), "vbox15" ),
    ( "/apps/gnome-screensaver/user_switch_enabled", _("Allow user _switching"), "vbox15" )
)

class PessulusMainDialog:
    (
        COLUMN_NAME,
        COLUMN_ICON,
        COLUMN_PAGENUMBER
    ) = range (3)

    def __init__ (self, applier, quit_on_close = True):
        globalvar.applier = applier

        self.quit_on_close = quit_on_close

        for gconfdir in gconfdirs:
            globalvar.applier.add_dir (gconfdir, gconf.CLIENT_PRELOAD_NONE)

        self.builder = gtk.Builder()
        self.builder.set_translation_domain(PACKAGE)
        self.builder.add_from_file(os.path.join (BUILDERDIR, "pessulus.ui"))

        self.window = self.builder.get_object ("dialogEditor")
        self.window.connect ("response", self.__on_dialog_response)

        if self.quit_on_close:
            self.window.connect ("destroy", self.__on_dialog_destroy)
        else:
            self.window.connect ("delete-event", gtk.Widget.hide_on_delete)

        self.__init_checkbuttons ()
        self.__init_disabledapplets ()
        self.__init_safeprotocols ()
        self.__init_pageselector ()

        self.window.show ()

    def __init_checkbuttons (self):
        for (key, string, box_str) in lockdownbuttons:
            button = lockdowncheckbutton.PessulusLockdownCheckbutton.new (key,
                                                                          string)
            box = self.builder.get_object (box_str)
            box.pack_start (button.get_widget (), False)

    def __init_disabledapplets (self):
        treeview = self.builder.get_object ("treeviewDisabledApplets")
        button = self.builder.get_object ("buttonDisabledApplets")
        ldbutton = lockdownbutton.PessulusLockdownButton.new_with_widget (button)
        self.disabledapplets = disabledapplets.PessulusDisabledApplets (treeview,
                                                                        ldbutton)

    def __init_safeprotocols (self):
        button = self.builder.get_object ("buttonDisableUnsafeProtocols")
        checkbutton = self.builder.get_object ("checkbuttonDisableUnsafeProtocols")

        lockdown = lockdowncheckbutton.PessulusLockdownCheckbutton.new_with_widgets (
                    "/apps/epiphany/lockdown/disable_unsafe_protocols",
                    button, checkbutton)

        hbox = self.builder.get_object ("hboxSafeProtocols")

        treeview = self.builder.get_object ("treeviewSafeProtocols")
        addbutton = self.builder.get_object ("buttonSafeProtocolAdd")
        editbutton = self.builder.get_object ("buttonSafeProtocolEdit")
        removebutton = self.builder.get_object ("buttonSafeProtocolRemove")

        self.safeprotocols = safeprotocols.PessulusSafeProtocols (lockdown.get_lockdownbutton (),
                                                                  treeview,
                                                                  addbutton,
                                                                  editbutton,
                                                                  removebutton)

        checkbutton.connect ("toggled", self.__on_unsafeprotocols_toggled, hbox)
        self.__on_unsafeprotocols_toggled (checkbutton, hbox)

    def __init_pageselector (self):
        use_tree = False
        if use_tree:
            store = gtk.TreeStore (str, str, int)
        else:
            store = gtk.ListStore (str, str, int)

        notebook = self.builder.get_object ("notebook2")
        children = notebook.get_children ()

        for (name, icon, widgetname) in pages:
            i = 0
            found = False
            for child in children:
                if child == self.builder.get_object (widgetname):
                    found = True
                    break
                i += 1

            if not found:
                continue

            if use_tree:
                iter = store.append (None)
            else:
                iter = store.append ()

            store.set (iter,
                       self.COLUMN_ICON, icon,
                       self.COLUMN_NAME, name,
                       self.COLUMN_PAGENUMBER, i)

        pageselector = self.builder.get_object ("pageselector")
        pageselector.set_model (store)

        col = gtk.TreeViewColumn ()
        pageselector.append_column (col)

        cell = gtk.CellRendererPixbuf ()
        col.pack_start (cell, True)
        col.add_attribute (cell, 'icon_name', self.COLUMN_ICON)

        cell = gtk.CellRendererText ()
        col.pack_start (cell, True)
        col.add_attribute (cell, 'text', self.COLUMN_NAME)
 
        pageselector.connect ("cursor-changed", self.__on_page_select,
                              notebook)
        pageselector.set_cursor ((0,))

    def __on_unsafeprotocols_toggled (self, checkbutton, hbox):
        sensitive = checkbutton.get_active ()
        hbox.set_sensitive (sensitive)
        self.safeprotocols.set_sensitive (sensitive)

    def __on_page_select (self, selector, notebook):
        model = selector.get_model()
        iter = model.get_iter (selector.get_cursor ()[0])
        notebook.set_current_page (model[iter][self.COLUMN_PAGENUMBER])

    def __error_dialog (self, primary, secondary = None):
        def __on_response (dialog, response_id):
            dialog.destroy ()

        dialog = gtk.MessageDialog (parent = self.window,
                                    flags = gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                    type = gtk.MESSAGE_ERROR,
                                    buttons = gtk.BUTTONS_CLOSE,
                                    message_format = primary)
        if secondary:
            dialog.format_secondary_text (secondary)

        dialog.connect ("response", __on_response)
        dialog.show ()

    def __on_dialog_response (self, dialog, response_id):
        if dialog == self.window and response_id == gtk.RESPONSE_HELP:
            doc_id = "system-admin-guide"
            uri = "ghelp:%s#lockdown" % doc_id

            try:
                gtk.show_uri (self.window.get_screen(), uri,
                              gtk.get_current_event_time())
            except gobject.GError, e:
                primary = _("Could not display help document '%s'") % escape_pango (doc_id)
                self.__error_dialog (primary, str (e))
            return
        
        dialog.hide ()
        if self.quit_on_close:
            dialog.destroy ()

    def __on_dialog_destroy (self, dialog):
        for gconfdir in gconfdirs:
            globalvar.applier.remove_dir (gconfdir)

        gtk.main_quit ()
