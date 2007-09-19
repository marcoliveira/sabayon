#
# Copyright (C) 2005 Red Hat, Inc.
# Copyright (C) 2004 GNOME Foundation
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

#
# All the text was copied from gedit-close-confirmation-dialog.c
#

import gtk
import gettext

class SaveConfirmationAlert (gtk.MessageDialog):
    def __init__ (self, parent_window, profile_name, seconds):
        gtk.MessageDialog.__init__ (self, parent_window, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE)

        self.set_destroy_with_parent (True)
        self.set_title ("")

        self.add_button (_("Close _Without Saving"), gtk.RESPONSE_NO)
        self.add_button (gtk.STOCK_CANCEL,           gtk.RESPONSE_CANCEL)
        self.add_button (gtk.STOCK_SAVE,             gtk.RESPONSE_YES)

        self.set_default_response (gtk.RESPONSE_YES)

        self.set_markup ("<b>" +
                         _("Save changes to profile \"%s\" before closing?") % profile_name
                         + "</b>")

        if seconds < 55:
            secondary_msg = ngettext ("If you don't save, changes from the last %ld second "
                                      "will be permanently lost.",
                                      "If you don't save, changes from the last %ld seconds "
                                      "will be permanently lost.",
                                      seconds) % seconds
        elif seconds < 75:
            secondary_msg = _("If you don't save, changes from the last minute will be permanently lost.")
            
        elif seconds < 110:
            seconds -= 60
            secondary_msg = ngettext ("If you don't save, changes from the last minute and %ld "
                                      "second will be permanently lost.",
                                      "If you don't save, changes from the last minute and %ld "
                                      "seconds will be permanently lost.",
                                      seconds) % seconds
        elif seconds < 3600:
            minutes = seconds / 60
            secondary_msg = ngettext ("If you don't save, changes from the last %ld minute "
                                      "will be permanently lost.",
                                      "If you don't save, changes from the last %ld minutes "
                                      "will be permanently lost.",
                                      minutes) % minutes
        elif seconds < 7200:
            seconds -= 3600;
            minutes = seconds / 60;
            if minutes < 5:
                secondary_msg = _("If you don't save, changes from the last hour "
                                  "will be permanently lost.")
            else:
                secondary_msg = ngettext ("If you don't save, changes from the last hour and %d "
                                          "minute will be permanently lost.",
                                          "If you don't save, changes from the last hour and %d "
                                          "minutes will be permanently lost.",
                                          minutes) % minutes
        else:
            hours = seconds / 3600;
            secondary_msg = ngettext ("If you don't save, changes from the last %d hour "
                                      "will be permanently lost.",
                                      "If you don't save, changes from the last %d hours "
                                      "will be permanently lost.",
                                      hours) % hours
                                                            
        self.format_secondary_text (secondary_msg)
