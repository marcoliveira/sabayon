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

import sys

from HTMLParser import HTMLParser

debug = 0
indent = '    '

TYPE_FOLDER = 1
TYPE_BOOKMARK = 2

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

class Bookmark:
    def __init__(self, folder, name):
        self.folder = folder
        self.name = name
        self.attrs = {}

    def get_attr(self, name):
        return self.attrs.get(name, None)

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

class BookmarkFolder:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.attrs = {}
        self.folders = []
        self.bookmarks = []

    def add_folder(self, name):
        folder = BookmarkFolder(name, self)
        self.folders.append(folder)
        return folder

    def add_bookmark(self, name):
        bookmark = Bookmark(self, name)
        self.bookmarks.append(bookmark)
        return bookmark

    def set_attr(self, name, value):
        self.attrs[name] = value

    def get_attr(self, name):
        return self.attrs.get(name, None)

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
        
    def _traverse(self, visit_func, path, data):
        visit_func(self, path, data)
        path.append(self)
        for folder in self.folders:
            folder._traverse(visit_func, path, data)
        path.pop()

    def traverse(self, visit_func, data=None):
        path = []
        self._traverse(visit_func, path, data)


    def find_bookmark(self, name):
        result = []

        def visit(folder, path, data):
            for bookmark in folder.bookmarks:
                if bookmark.name == name:
                    result.append(bookmark)

        self.traverse(visit)
        return result
    
# ----------------------------------

class HTMLTag:
    def __init__(self, tag):
        self.tag = tag
        self.attrs = {}
        self.data = ""

class BookmarkHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.stack = [HTMLTag("None")]
        self.folder_root = None
        self.cur_folder = self.folder_root

    def stack_to_string(self):
        return "%s" % [ s.tag for s in self.stack ]

    def find_tag_on_stack(self, tag):
        i = len(self.stack) - 1
        while i >= 0:
            if self.stack[i].tag == tag:
                return self.stack[i]
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
                assert not self.folder_root and top.tag == 'h1'
                self.folder_root = BookmarkFolder(top.data, None)
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
def visit(folder, path, data=None):
    max_len = 80
    path = folder.path()
    level = len(path)-1
    print "%sFolder: %s(%s) path = [%s]" % (indent*level,
                                            folder.name[0:max_len],
                                            data, folder.path_as_names(" -> "))
    for attr, value in folder.attrs.items():
        print "%sAttr: %s = %s" % (indent*(level+1), attr, value[0:max_len])

    for bookmark in folder.bookmarks:
        print "%sBookmark: %s" % (indent*(level+1), bookmark.name[0:max_len])
        for attr, value in bookmark.attrs.items():
            print "%sAttr: %s = %s" % (indent*(level+2), attr, value[0:max_len])

# -----------------------

if __name__ == "__main__":
    parser = BookmarkHTMLParser()

    parser.feed(open('bookmarks.html').read())
    parser.close()

    bm_name = "libical"
    bm_list = parser.folder_root.find_bookmark(bm_name)
    if bm_list:
        for bm in bm_list:
            print "found bookmark %s url=%s" % (bm.name, bm.get_attr("href"))
            print "path = %s" % bm.path_as_names(" -> ")
        else:
            print "%s not found" % bm_name

    parser.folder_root.traverse(visit)
