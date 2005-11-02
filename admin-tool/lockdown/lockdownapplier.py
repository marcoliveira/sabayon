#!/usr/bin/env python

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

class PessulusLockdownApplier:
    def __init__ (self):
        raise NotImplementedError

    def supports_mandatory_settings (self):
        raise NotImplementedError

    def get_schema (self, key):
        raise NotImplementedError

    def get_bool (self, key):
        raise NotImplementedError

    def set_bool (self, key, value, mandatory):
        raise NotImplementedError

    def get_list (self, key, list_type):
        raise NotImplementedError

    def set_list (self, key, list_type, value, mandatory):
        raise NotImplementedError

    def key_is_writable (self, key):
        raise NotImplementedError

    def notify_add (self, key, handler, data = None):
        raise NotImplementedError

    def notify_remove (self, monitor):
        raise NotImplementedError

    def add_dir (self, dir, preloadtype):
        raise NotImplementedError

    def remove_dir (self, dir):
        raise NotImplementedError
