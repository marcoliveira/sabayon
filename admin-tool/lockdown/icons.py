#!/usr/bin/env python

# vim: set ts=4 sw=4 et:

#
# Copyright (C) 2005 Vincent Untz <vuntz@gnome.org>
#
# This is based on code from gnome-menus (in menutreemodel.py)
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
import gtk

def load_icon_from_path (icon_path):
    if os.path.isfile (icon_path):
        try:
            return gtk.gdk.pixbuf_new_from_file_at_size (icon_path, 24, 24)
        except:
            pass
    return None

def load_icon_from_data_dirs (icon_value):
    data_dirs = None
    if os.environ.has_key ("XDG_DATA_DIRS"):
        data_dirs = os.environ["XDG_DATA_DIRS"]
    if not data_dirs:
        data_dirs = "/usr/local/share/:/usr/share/"

    for data_dir in data_dirs.split (":"):
        retval = load_icon_from_path (os.path.join (data_dir, "pixmaps", icon_value))
        if retval:
            return retval
        retval = load_icon_from_path (os.path.join (data_dir, "icons", icon_value))
        if retval:
            return retval
    
    return None

def load_icon (icon_theme, icon_value):
    if not icon_value:
        return

    if os.path.isabs (icon_value):
        icon = load_icon_from_path (icon_value)
        if icon:
            return icon
        icon_name = os.path.basename (icon_value)
    else:
        icon_name = icon_value
    
    if icon_name.endswith (".png"):
        icon_name = icon_name[:-len (".png")]
    elif icon_name.endswith (".xpm"):
        icon_name = icon_name[:-len (".xpm")]
    elif icon_name.endswith (".svg"):
        icon_name = icon_name[:-len (".svg")]
    
    try:
        return icon_theme.load_icon (icon_name, 24, 0)
    except:
        return load_icon_from_data_dirs (icon_value)
