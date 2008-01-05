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
import gtk.glade

from config import *

from sabayon import errors
from sabayon import debuglog
import disabledapplets
import lockdownbutton
import lockdowncheckbutton
import lockdowncombo
import globalvar
import safeprotocols

gettext.install (PACKAGE, LOCALEDIR)

gconfdirs = [
"/desktop/gnome/lockdown",
"/apps/openoffice/lockdown",
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
    ( "/apps/panel/global/disable_lock_screen", _("Disable lock _screen"), "vbox8" ),
    ( "/apps/panel/global/disable_log_out", _("Disable log _out"), "vbox8" ),

    ( "/apps/epiphany/lockdown/disable_quit", _("Disable _quit"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_arbitrary_url", _("Disable _arbitrary URL"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_bookmark_editing", _("Disable _bookmark editing"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_history", _("Disable _history"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_javascript_chrome", _("Disable _javascript chrome"), "vbox9" ),
    ( "/apps/epiphany/lockdown/disable_toolbar_editing", _("Disable _toolbar editing"), "vbox9" ),
    ( "/apps/epiphany/lockdown/fullscreen", _("_Fullscreen"), "vbox9" ),
    ( "/apps/epiphany/lockdown/hide_menubar", _("Hide _menubar"), "vbox9" ),

    # Translators: OO.o normally saves personal information (name/email of author, etc.) to files.
    # This can be used to disable this, for when you don't want people to know you created the document.
    ( "/apps/openoffice/lockdown/remove_personal_info_on_save", _("Remove personal info from documents when saving them"), "ooosecurity" ),
    ( "/apps/openoffice/lockdown/warn_info_create_pdf", _("Warn if macro tries to create a PDF"), "ooosecurity" ),
    ( "/apps/openoffice/lockdown/warn_info_printing",   _("Warn if macro tries to print a document"), "ooosecurity" ),
    ( "/apps/openoffice/lockdown/warn_info_saving", _("Warn if macro tries to save a document"), "ooosecurity" ),
    ( "/apps/openoffice/lockdown/warn_info_signing", _("Warn if macro tries to sign a document"), "ooosecurity" ),
    ( "/apps/openoffice/lockdown/recommend_password_on_save", _("Recommend password when saving a document"), "ooosecurity" ),

    ( "/apps/openoffice/auto_save", _("Enable auto-save"), "oooio" ),
#    ( "/apps/openoffice/auto_save_interval", _("Auto save interval"), "oooio" ),
    ( "/apps/openoffice/printing_modifies_doc", _("Printing should mark the document as modified"), "oooio" ),
    ( "/apps/openoffice/use_system_file_dialog", _("Use system's file dialog"), "oooio" ),
    ( "/apps/openoffice/create_backup", _("Create backup copy on save"), "oooio" ),
    ( "/apps/openoffice/warn_alien_format", _("Warn when saving non-OpenOffice.org formats"), "oooio" ),

    ( "/apps/openoffice/use_opengl", _("Use OpenGL"), "oooui" ),
    ( "/apps/openoffice/use_system_font", _("Use system font"), "oooui" ),
    ( "/apps/openoffice/use_font_anti_aliasing", _("Use anti-aliasing"), "oooui" ),
    ( "/apps/openoffice/lockdown/disable_ui_customization", _("Disable UI customization"), "oooui" ),
    ( "/apps/openoffice/show_menu_inactive_items", _("Show insensitive menu items"), "oooui" ),
    ( "/apps/openoffice/show_font_preview", _("Show font preview"), "oooui" ),
    ( "/apps/openoffice/show_font_history", _("Show font history") , "oooui" ),
    ( "/apps/openoffice/show_menu_icons", _("Show icons in menus"), "oooui" ),
# Unclear / minority:
#   ( "/apps/openoffice/optimize_opengl", , "oooui" ),
#   ( "/apps/openoffice/font_anti_aliasing_min_pixel", , "oooui" ),
)

lockdowncombos = (
    ( "/apps/openoffice/lockdown/macro_security_level", "macroSecurityLevel", "int",
      [ "3", "2", "1", "0" ] ),
    ( "/apps/openoffice/writer_default_document_format", "writerDefaultFormat", "string",
      [ "writer8", "MS Word 97", "StarOffice XML (Writer)" ] ),
    ( "/apps/openoffice/calc_default_document_format", "calcDefaultFormat", "string",
      [ "calc8", "MS Excel 97", "StarOffice XML (Calc)" ] ),
    ( "/apps/openoffice/impress_default_document_format", "impressDefaultFormat", "string",
      [ "impress8", "MS PowerPoint 97", "StarOffice XML (Impress)" ] ),
    ( "/apps/openoffice/icon_size", "defaultIconSize", "int",
      [ "2", "1", "0" ] ),
    ( "/apps/openoffice/undo_steps", "undoSteps", "int",
      [ "5", "10", "25", "50" ] )
)

class PessulusMainDialog:
    def __init__ (self, applier, quit_on_close = True):
        globalvar.applier = applier
        globalvar.tooltips = gtk.Tooltips ()

        self.quit_on_close = quit_on_close

        for gconfdir in gconfdirs:
            globalvar.applier.add_dir (gconfdir, gconf.CLIENT_PRELOAD_NONE)

        self.glade_file = os.path.join (GLADEDIR, "pessulus.glade")
        self.xml = gtk.glade.XML (self.glade_file, "dialogEditor", PACKAGE)

        self.__init_combos ()
        self.__init_checkbuttons ()
        self.__init_disabledapplets ()
        self.__init_safeprotocols ()

        self.xml.get_widget ("helpbutton").set_sensitive (False)

        self.window = self.xml.get_widget ("dialogEditor")
        self.window.connect ("response", self.__on_dialog_response)

        if self.quit_on_close:
            self.window.connect ("destroy", self.__on_dialog_destroy)
        else:
            self.window.connect ("delete-event", gtk.Widget.hide_on_delete)

        self.window.show ()

    def __init_checkbuttons (self):
        for (key, string, box_str) in lockdownbuttons:
            button = lockdowncheckbutton.PessulusLockdownCheckbutton.new (key,
                                                                          string)
            box = self.xml.get_widget (box_str)
            box.pack_start (button.get_widget (), False)

    def __init_combos (self):
        for (key, combo_str, type, value_list) in lockdowncombos:
            combo = self.xml.get_widget (combo_str)
            button = self.xml.get_widget (combo_str + "Button")
            lockdowncombo.PessulusLockdownCombo.attach (combo, button, key, type, value_list)

    def __init_disabledapplets (self):
        treeview = self.xml.get_widget ("treeviewDisabledApplets")
        button = self.xml.get_widget ("buttonDisabledApplets")
        ldbutton = lockdownbutton.PessulusLockdownButton.new_with_widget (button)
        self.disabledapplets = disabledapplets.PessulusDisabledApplets (treeview,
                                                                        ldbutton)

    def __init_safeprotocols (self):
        button = self.xml.get_widget ("buttonDisableUnsafeProtocols")
        checkbutton = self.xml.get_widget ("checkbuttonDisableUnsafeProtocols")

        lockdown = lockdowncheckbutton.PessulusLockdownCheckbutton.new_with_widgets (
                    "/apps/epiphany/lockdown/disable_unsafe_protocols",
                    button, checkbutton)

        hbox = self.xml.get_widget ("hboxSafeProtocols")

        treeview = self.xml.get_widget ("treeviewSafeProtocols")
        addbutton = self.xml.get_widget ("buttonSafeProtocolAdd")
        editbutton = self.xml.get_widget ("buttonSafeProtocolEdit")
        removebutton = self.xml.get_widget ("buttonSafeProtocolRemove")

        self.safeprotocols = safeprotocols.PessulusSafeProtocols (lockdown.get_lockdownbutton (),
                                                                  treeview,
                                                                  addbutton,
                                                                  editbutton,
                                                                  removebutton)

        checkbutton.connect ("toggled", self.__on_unsafeprotocols_toggled, hbox)
        self.__on_unsafeprotocols_toggled (checkbutton, hbox)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __on_unsafeprotocols_toggled (self, checkbutton, hbox):
        sensitive = checkbutton.get_active ()
        debuglog.uprint ("PessulusMainDialog: setting unsafe protocols toggle to %s", sensitive)
        hbox.set_sensitive (sensitive)
        self.safeprotocols.set_sensitive (sensitive)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def __on_dialog_response (self, dialog, response_id):
        if dialog == self.window and response_id == gtk.RESPONSE_HELP:
            return
        
        dialog.hide ()
        if self.quit_on_close:
            dialog.destroy ()

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_PESSULUS)
    def __on_dialog_destroy (self, dialog):
        for gconfdir in gconfdirs:
            globalvar.applier.remove_dir (gconfdir)

        gtk.main_quit ()
