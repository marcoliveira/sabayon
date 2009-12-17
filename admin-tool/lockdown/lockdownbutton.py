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

import globalvar

def load_image (name):
    image = gtk.Image ()
    image.set_from_icon_name (name, gtk.ICON_SIZE_MENU)
    image.show ()
    return image

class PessulusLockdownButton (gobject.GObject):

    __gsignals__ = {
        "toggled" : ( gobject.SIGNAL_RUN_LAST, None, (gobject.TYPE_BOOLEAN,) )
    }

    def __init__ (self):
        gobject.GObject.__init__(self)

        self.locked = False
        self.button = None

        self.locked_image = load_image ("stock_lock")
        self.unlocked_image = load_image ("stock_lock-open")

    def new ():
        lockdownbutton = PessulusLockdownButton ()

        lockdownbutton.button = gtk.Button ()
        lockdownbutton.button.show ()

        lockdownbutton.__connect_and_update ()
        return lockdownbutton
    new = staticmethod (new)

    def new_with_widget (button):
        lockdownbutton = PessulusLockdownButton ()

        lockdownbutton.button = button
        child = button.get_child ()

        if child is not None:
            button.remove (child)

        lockdownbutton.__connect_and_update ()
        return lockdownbutton
    new_with_widget = staticmethod (new_with_widget)

    def get_widget (self):
        return self.button

    def get (self):
        return self.locked

    def set (self, bool):
        if self.locked != bool:
            self.locked = bool
            self.emit ("toggled", self.locked)

        self.__update ()

    def __connect_and_update (self):
        self.button.set_relief (gtk.RELIEF_NONE)
        self.button.connect ("clicked", self.__on_button_clicked)

        self.set (False)

        if globalvar.applier.supports_mandatory_settings ():
            self.button.show ()
        else:
            self.button.hide ()

    def __update (self):
        self.__set_button_icon ()
        self.__set_tooltip ()

    def __set_tooltip (self):
        if self.locked:
            tooltip = _("Click to make this setting not mandatory")
        else:
            tooltip = _("Click to make this setting mandatory")

        self.button.set_tooltip_text (tooltip)

    def __set_button_icon (self):
        if self.locked:
            newimage = self.locked_image
        else:
            newimage = self.unlocked_image

        child = self.button.get_child ()
        if child != newimage:
            if child != None:
                self.button.remove (child)
            self.button.add (newimage)

    def __on_button_clicked (self, button):
        self.locked = not self.locked
        self.__update ()

        self.emit ("toggled", self.locked)

if gtk.pygtk_version < (2, 8, 0):
    gobject.type_register (PessulusLockdownButton)
