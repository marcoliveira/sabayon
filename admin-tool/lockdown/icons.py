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

def fix_icon_name (icon_name):
    if not icon_name:
        return None

    if icon_name.endswith (".png"):
        icon_name = icon_name[:-len (".png")]
    elif icon_name.endswith (".xpm"):
        icon_name = icon_name[:-len (".xpm")]
    elif icon_name.endswith (".svg"):
        icon_name = icon_name[:-len (".svg")]
    
    return icon_name
