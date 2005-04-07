#!/usr/bin/env python

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

# XXX - TODO:
# add support for DD tags
# add support for HR format tags

import sys
import os
import re
from HTMLParser import HTMLParser

try:
    import util
    import config
except:
    from sabayon import util
    from sabayon import config

debug = 0
indent = '    '

bookmark_separator = "/"
TYPE_FOLDER     = 1
TYPE_BOOKMARK   = 2
TYPE_FOLDER_END = 3

tag_info_dict = {
    'dt' : {'implicit_close_event' : ['begin'],
            'implicit_close_scope' : ['dl'],
            'implicit_close_tags'  : ['dt', 'dd']},
    'dd' : {'implicit_close_event' : ['begin'],
            'implicit_close_scope' : ['dl'],
            'implicit_close_tags'  : ['dd']},
    'dl' : {'implicit_close_event' : ['begin', 'end'],
            'implicit_close_scope' : ['dl'],
            'implicit_close_tags'  : ['dt', 'dd']},
    'p'  : {'simple_tag'           : True},
    'hr' : {'simple_tag'           : True},
}

# XXX - these should be defined one place
LOG_OPERATION           = 0x00001
LOG_CHANGE              = 0x00002
LOG_IGNORED_CHANGE      = 0x00004
LOG_APPLY               = 0x00008
LOG_SYNC                = 0x00010
LOG_PARSE               = 0x00020
LOG_PREF                = 0x00040
LOG_FILE_CONTENTS       = 0x00080
LOG_DATA                = 0x00100
LOG_VERBOSE             = 0x10000

def dprint(mask, fmt, *args):
    util.debug_print(util.DEBUG_MOZILLASOURCE, fmt % args, mask)

class Bookmark:
    def __init__(self, folder, name):
        self.folder = folder
        self.name = name
        self.attrs = {}

    def get_attr(self, name):
        return self.attrs.get(name, None)

    def get_url(self):
        return self.attrs.get("href", None)

    def path(self):
        path = self.folder.path()
        path.append(self)
        return path

    def path_as_names(self, join=None):
        path = self.folder.path_as_names()
        path.append(self.name)
        if join == None:
            return path
        else:
            return join.join(path)

    def path_as_string(self):
        return self.path_as_names(bookmark_separator)                       

class BookmarkFolder:
    def __init__(self, name, parent):
        self.reset(name, parent)

    def reset(self, name, parent):
        self.name = name
        self.parent = parent
        self.attrs = {}
        self.entries = []

    def entry_index(self, entry):
        n_entries = len(self.entries)
        i = 0
        while (i < n_entries):
            if self.entries[i] == entry:
                return i
            i += 1
        return None

    def add_entry(self, entry):
        self.entries.append(entry)
        return entry

    def add_folder(self, folder):
        if not isinstance(folder, BookmarkFolder):
            folder = BookmarkFolder(folder, self)
        self.entries.append(folder)
        return folder

    def lookup_folder(self, folder):
        for entry in self.entries:
            if isinstance(entry, BookmarkFolder):
                if entry == folder:
                    return entry
        return None

    def add_bookmark(self, bookmark):
        if not isinstance(bookmark, Bookmark):
            bookmark = Bookmark(self, bookmark)
        self.entries.append(bookmark)
        return bookmark


    def lookup_bookmark(self, bookmark):
        for entry in self.entries:
            if isinstance(entry, Bookmark):
                if entry == bookmark:
                    return entry
        return None

    def lookup_path(self, path):
        path_len = len(path)
        i = 0
        folder = self
        while i < path_len - 1:
            folder = folder.lookup_folder(path[i])
            if not folder:
                return None
            i += 1
        entry_index = folder.entry_index(path[i])
        if entry_index == None:
            return None
        else:
            return folder.entries[entry_index]
                    

    def add_path_entry(self, path, entry):
        path_len = len(path)
        i = 0
        parent = folder = self
        while i < path_len - 1:
            folder = parent.lookup_folder(path[i])
            if not folder:
                folder = parent.add_folder(path[i])
            parent = folder
            i += 1
        if folder.entry_index(path[i]) == None:
            folder.add_entry(path[i])
        

    def set_attr(self, name, value):
        self.attrs[name] = value

    def get_attr(self, name):
        return self.attrs.get(name, None)

    def get_url(self):
        return self.attrs.get("href", None)

    def path(self):
        path = [self]
        folder = self
        parent = self.parent
        while parent:
            path.append(parent)
            parent = parent.parent
        path.reverse()
        return path
    
    def path_as_names(self, join=None):
        path = self.path()
        path = [ p.name for p in path ]
        if join == None:
            return path
        else:
            return join.join(path)
        
    def path_as_string(self):
        return self.path_as_names(bookmark_separator)                       

    def _traverse(self, visit_func, path, data):
        assert isinstance(self, BookmarkFolder)

        path.append(self)
        for entry in self.entries:
            if isinstance(entry, BookmarkFolder):
                visit_func(entry, TYPE_FOLDER, path, data)
                entry._traverse(visit_func, path, data)
            elif isinstance(entry, Bookmark):
                visit_func(entry, TYPE_BOOKMARK, path, data)
            else:
                raise ValueError
        path.pop()
        visit_func(self, TYPE_FOLDER_END, path, data)

    def traverse(self, visit_func, data=None):
        path = []
        self._traverse(visit_func, path, data)


    def find_bookmark(self, name):
        result = []

        def visit(entry, type, path, data):
            if type == TYPE_BOOKMARK:
                if entry.name == name:
                    result.append(entry)

        self.traverse(visit)
        return result
    
# ----------------------------------

class HTMLTag:
    def __init__(self, tag):
        self.tag = tag
        self.attrs = {}
        self.data = ""

class BookmarkHTMLParser(HTMLParser):
    def __init__(self, root=None):
        HTMLParser.__init__(self)
        self.stack = [HTMLTag("None")]
        self.folder_root = root
        self.cur_folder = self.folder_root

    def set_root(self, root):
        self.folder_root = root

    def get_root(self):
        return self.folder_root

    def stack_to_string(self):
        return "%s" % [ s.tag for s in self.stack ]

    def find_tag_on_stack(self, tag):
        i = len(self.stack) - 1
        while i >= 0:
            if self.stack[i].tag == tag:
                return self.stack[i]
            i -= 1
        return None

    def implicit_close(self, event, tag):
        
        tag_info = tag_info_dict.get(tag, None)
        if not tag_info:
            return
        
        implicit_close_event = tag_info.get('implicit_close_event', None)
        if not implicit_close_event or not event in implicit_close_event:
            return

        implicit_close_scope = tag_info.get('implicit_close_scope', None)
        implicit_close_tags  = tag_info.get('implicit_close_tags',  None)
        if not (implicit_close_scope or implict_close_tags):
            return
        
        scope_index = len(self.stack) - 1
        while scope_index >= 0:
            if self.stack[scope_index].tag in implicit_close_scope:
                break
            scope_index = scope_index - 1

        i = scope_index + 1
        while i < len(self.stack):
            if self.stack[i].tag in implicit_close_tags:
                break
            i = i + 1

        j = len(self.stack) - 1
        while (j >= i):
            self._handle_endtag(self.stack[j].tag)
            j = j - 1


    def handle_starttag(self, tag, attrs):
        self.implicit_close('begin', tag)
        
        tag_info = tag_info_dict.get(tag, None)
        if not tag_info:
            simple_tag = False
        else:
            simple_tag = tag_info.get('simple_tag', False)
        if not simple_tag:
            top = HTMLTag(tag)
            for attr, value in attrs:
                top.attrs[attr] = value
            self.stack.append(top)

    def _handle_endtag(self, tag):
        top = self.stack.pop();
        if tag == "a":
            bookmark = self.cur_folder.add_bookmark(top.data)
            for attr, value in top.attrs.items():
                bookmark.attrs[attr] = value
            if debug:
                print "%sBookmark %s" % (indent*(len(self.cur_folder.path())),top.data)

        elif top.tag == 'h3' or top.tag == 'h1':
            # Folders are contained in a <DT><H3 attrs>name</H3> sequence
            # Note, this is currently the only use of the H3 tag in a bookmark
            # file so rather than looking for the aforementioned sequence an
            # easy "hack" is to just look for an H3 tag, its attrs, and its
            # data will be the folder name. Note <H1> is reserved for the
            # root folder.
            #
            # Since this is a new folder, we add it as a folder to the
            # currently open folder, it is effectively a push of the folder
            # stack, but we maintain it as simply the currently open folder.
            if top.tag == 'h3':
                self.cur_folder = self.cur_folder.add_folder(top.data)
            else:
                # Tag is h1, must be the root folder
                self.folder_root.reset(top.data, None)
                self.cur_folder = self.folder_root
            for attr, value in top.attrs.items():
                self.cur_folder.attrs[attr] = value
            if debug:
                print "%sPUSH Folder %s" % (indent*(len(self.cur_folder.path())-1),self.cur_folder.name)
        elif top.tag == 'dl':
            # Closing current folder, effectively pop it off the folder stack,
            # the currently open folder is replaced by this folders parent.
            if debug:
                print "%sPOP Folder %s" % (indent*(len(self.cur_folder.path())-1),self.cur_folder.name)
            self.cur_folder = self.cur_folder.parent
        else:
            pass

            


    def handle_endtag(self, tag):
        self.implicit_close('end', tag)
        assert tag == self.stack[-1].tag
        self._handle_endtag(tag)

    def handle_data(self, data):
        tag = self.stack[-1]
        data = data.strip()
        tag.data = tag.data + data

# -----------------------
def visit(entry, type, path, data=None):
    max_len = 80
    level = len(path)-1

    if type == TYPE_FOLDER:
        print "%sFolder: %s(%s) path = [%s]" % (indent*level,
                                                entry.name[0:max_len],
                                                data, entry.path_as_string())
    elif type == TYPE_BOOKMARK:
        print "%sBookmark: %s" % (indent*(level), entry.name[0:max_len])
    elif type == TYPE_FOLDER_END:
        pass
    else:
        raise ValueError

    for attr, value in entry.attrs.items():
        print "%sAttr: %s = %s" % (indent*(level+1), attr, value[0:max_len])

# -----------------------

if __name__ == "__main__":
    bm_root = []
    bm_file = BookmarkHTMLParser()
    bm_file.set_root(bm_root)
    bm_file.feed(open('bookmarks.html').read())
    bm_file.close()

    bm_root_1 = []
    bm_file_1 = BookmarkHTMLParser(bm_root_1)
    bm_file_1.feed(open('bookmarks1.html').read())
    bm_file_1.close()

    if False:
        bm_name = "libical"
        bm_list = bm_file.folder_root.find_bookmark(bm_name)
        if bm_list:
            for bm in bm_list:
                print "found bookmark %s url=%s" % (bm.name, bm.get_attr("href"))
                print "path = %s" % bm.path_as_string()
        else:
            print "%s not found" % bm_name

    if False:
        bm_file.folder_root.traverse(visit)

    if True:
        bm_dict   = bm_file.folder_root.convert_to_dict()
        bm_dict_1 = bm_file_1.folder_root.convert_to_dict()

        dc = util.DictCompare(bm_dict, bm_dict_1)
        dc.compare()
        cs = dc.get_change_set('a', 'b')
        util.dump_change_set(cs)

    if False:
        bm_file.folder_root.write("tmp_bookmarks.html", exclude_attrs=exclude_attrs)

