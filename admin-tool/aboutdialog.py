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
import errors
import debuglog
from config import *

#
# Of course, this would all be so much easier if
# gtk_show_about_dialog() was wrapped
#

global_about_dialog = None

def show_about_dialog (parent_window = None):

    if parent_window:
        about_dialog = parent_window.get_data ("gtk-about-dialog")
    else:
        global global_about_dialog
        about_dialog = global_about_dialog

    if about_dialog:
        about_dialog.present ()
        return

    authors = [
        "Daniel Veillard <veillard@redhat.com>",
        "John Dennis <jdennis@redhat.com>",
        "Mark McLoughlin <markmc@redhat.com>"
    ]

    # documenters = [
    # ]

    about_dialog = gtk.AboutDialog ()

    if parent_window:
        about_dialog.set_transient_for (parent_window)
    about_dialog.set_destroy_with_parent (True)
    about_dialog.set_icon_name ("sabayon")

    about_dialog.set_name               (PACKAGE)
    about_dialog.set_version            (VERSION)
    about_dialog.set_copyright          ("(C) 2005 Red Hat, Inc.")
    about_dialog.set_website            ("http://www.gnome.org/projects/sabayon")
    about_dialog.set_comments           (_("Program to establish and edit profiles for users"))
    about_dialog.set_authors            (authors)
    about_dialog.set_logo_icon_name     ("sabayon")
    about_dialog.set_translator_credits (_("translator-credits"))

    # about_dialog.set_documenters        (documenters)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def handle_delete (about, event):
        about.hide ()
        return True
    about_dialog.connect ("delete-event", handle_delete)

    @errors.checked_callback (debuglog.DEBUG_LOG_DOMAIN_USER)
    def handle_response (about, response):
        about.hide ()
    about_dialog.connect ("response", handle_response)

    about_dialog.present ()

    if parent_window:
        parent_window.set_data ("gtk-about-dialog", about_dialog)
    else:
        global_about_dialog = about_dialog
