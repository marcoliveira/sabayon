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

import zipfile
import os
import os.path
import libxml2
import time
import socket
import sys
import tempfile
import shutil
import util

def dprint(fmt, *args):
    util.debug_print(util.DEBUG_STORAGE, fmt % args)

class ProfileStorageException(Exception):
    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)

class ProfileStorage:
    def __init__ (self, filename):
        dprint("init %s", filename)
        self.exists = False
	self.installed = False
	self.doc = None
	self.zipfile = None
	self.filename = filename
	self.filelist = None
        self.install_path = None
        
        if filename != None:
	    try:
	        os.stat(filename)
		self.exists = True
	    except:
	        pass
	    if self.exists:
	        if not zipfile.is_zipfile(filename):
	            raise ProfileStorageException("%s is not a storage file" %
		                                  filename)
		try:
		    self.zipfile = zipfile.ZipFile(filename, "a")
		except:
	            raise ProfileStorageException("Failed to read file %s" %
		                                  filename)
		self.__read_metadata()
	    else:
                dprint("New profile %s", filename)
	        self.doc = libxml2.newDoc("1.0")
		root = self.doc.newChild(None, "metadata", None)
		common = root.newChild(None, "common", None)
		files = root.newChild(None, "files", None)

    def __del__(self):
        if self.doc != None:
	    self.doc.freeDoc()
	    self.doc = None
	if self.zipfile != None:
	    self.zipfile.close()
	    self.zipfile = None

    def __read_metadata(self):
        if self.doc != None or self.zipfile == None:
	    return

        try:
	    metadata = self.zipfile.read("metadata")
	    doc = libxml2.readMemory(metadata, len(metadata), "metadata",
	                             None, libxml2.XML_PARSE_NOBLANKS)
	except:
	    raise ProfileStorageException("Failed to get metadata of %s" %
					  self.filename)
	root = doc.getRootElement()
	if root == None or root.name != "metadata":
	    doc.freeDoc()
	    raise ProfileStorageException("Broken metadata section in %s" %
					  self.filename)
        self.doc = doc
    
    def __update_metadata(self, log):
        try:
	    common = self.doc.xpathEval("/metadata/common")[0]
	except:
	    root = self.doc.getRootElement()
	    common = root.newChild(None, "common", None)
	try:
	    changelogs = common.xpathEval("changelogs")[0]
	except:
	    changelogs = common.newChild(None, "changelogs", None)
	if log == None:
	    return

	changelog = changelogs.children
	if changelog == None:
	    nlog = changelogs.newChild(None, "created", log)
	else:
	    nlog = self.doc.newDocNode(None, "changelog", log)
	    changelog.addPrevSibling(nlog)
	nlog.setProp("date", time.ctime(time.time()))
	nlog.setProp("user", util.get_user_name())
	nlog.setProp("host", socket.gethostname())

    def __update_file_metadata(self, file, log, handler = None,
                            description = None):
        try:
	    files = self.doc.xpathEval("/metadata/files")[0]
	except:
	    root = self.doc.getRootElement()
	    files = root.newChild(None, "files", None)
	try:
	    fil = files.xpathEval("file[@name='%s']" % (file))[0]
	except:
	    fil = files.newChild(None, "file", None)
	    fil.setProp("name", file)
	if handler != None:
	    fil.setProp("handler", handler)
	if description != None:
	    try:
		desc = fil.xpathEval("description")[0]
		desc.setContent(description)
	    except:
		fil.newChild(None, "description", description)
	if log == None:
	    return

	try:
	    changelogs = fil.xpathEval("changelogs")[0]
	except:
	    changelogs = fil.newChild(None, "changelogs", None)
	changelog = changelogs.children
	if changelog == None:
	    nlog = changelogs.newChild(None, "created", log)
	else:
	    nlog = self.doc.newDocNode(None, "changelog", log)
	    changelog.addPrevSibling(nlog)
	nlog.setProp("date", time.ctime(time.time()))
	nlog.setProp("user", util.get_user_name())
	nlog.setProp("host", socket.gethostname())
	    
    def __delete_file_metadata(self, file):
        try:
	    file = self.doc.xpathEval("/metadata/files/file[@name='%s']" %
	                               (file))[0]
	    file.unlinkNode()
	    file.freeNode()
	except:
	    pass

    def __get_metadata_handler(self, file):
        try:
	    handler = self.doc.xpathEval(
	       "string(/metadata/files/file[@name='%s']/@handler)" % file)
	except:
	    handler = ""
	return handler

    def __get_metadata_description(self, file):
        try:
	    description = self.doc.xpathEval(
	       "string(/metadata/files/file[@name='%s']/description)" % file)
	except:
	    description = ""
	return description

    def __get_file_info(self, file):
        return (file,
                self.__get_metadata_handler(file),
                self.__get_metadata_description(file))

    def __read_filelist(self):
        if self.filelist != None:
	    return self.filelist
	self.filelist = []
        if self.zipfile != None:
	    for info in self.zipfile.infolist():
	        if info.filename != 'metadata':
		    if not info.filename in self.filelist:
			self.filelist.append(info.filename)
	return self.filelist
        
    def __get_abs_filename(self, path):
        return os.path.join(os.path.abspath(self.install_path), path)
        
    #
    # Add an entry to the archive, set up the metadata
    # This won't write the change, use update_all() or update()
    # to commit the change to the target file.
    #
    def add_file(self, file, handler, description):
        dprint("add_file '%s' with description '%s' and handler '%s'",
               file, description, handler)
	if self.filelist == None:
	    self.__read_filelist()
	if not file in self.filelist:
	    self.filelist.append(file)
	self.__update_file_metadata(file, None, handler, description)

    #
    # Remove an entry from the archive, cleans up the associated metadata too
    # Returns 0 if this succeeded and -1 otherwise
    #
    def delete_file(self, file):
        dprint("delete_file(%s)", file)
	if file in self.filelist:
	    self.filelist.delete(file)
	    self.__delete_file_metadata(file)
	    return 0
	return -1


    #
    # Install the archive into a temporary directory
    # Returns the list of tupples (absolute file path, handler name)
    #
    def install(self):
        if self.installed:
            return
        
        self.install_path = tempfile.mkdtemp(prefix = ".profile-storage-%s-" % util.get_user_name())

        if not self.exists or not self.zipfile:
            self.installed = True
            return [] # Nothing to install
	
	res = []
	#
	# Try to walk first though all the paths to make sure everything
	# can be installed and not half of it
	# TODO: check for filesystem space left on the device.
	#
        for file in self.__read_filelist():
	    target = self.__get_abs_filename(file)
	    tardir = os.path.dirname(target)
	    if not os.path.isdir(tardir):
	        if os.path.exists(tardir):
		    raise ProfileStorageException("Cannot install %s since %s is not a directory" % (target, tardir))
		try:
		    os.makedirs(tardir)
                    dprint("created directory %s", tardir)
		except:
		    raise ProfileStorageException("Cannot create directory %s" % (tardir))
            if os.path.exists(tardir) and not os.access(tardir, os.W_OK):
		raise ProfileStorageException("Directory %s is not writable" % (tardir))
            if os.path.exists(target) and not os.access(target, os.W_OK):
		raise ProfileStorageException("File %s is not writable" % (target))
	
	for file in self.__read_filelist():
	    target = self.__get_abs_filename(file)
	    tardir = os.path.dirname(target)
	    data = self.zipfile.read(file)
            if os.path.exists(target):
                dprint("Overwriting %s", target)
            else:
                dprint("Creating %s", target)
	    try:
		f = open(target, "w");
		f.write(data)
		f.close()
	    except:
		raise ProfileStorageException("Failed to write to %s" % (target))
	    res.append(self.__get_file_info(file))
	    
	self.installed = True
        return res

    def uninstall(self):
        if self.installed:
            shutil.rmtree(self.install_path)
            self.install_path = None
            self.installed = False

    def get_install_path(self):
        return self.install_path

    #
    # Provides the list of entries in the archive along with some metadata
    # TODO: refine the metadata
    #
    def info_all(self):
        res = []
        for file in self.__read_filelist():
	    res.append(self.__get_file_info(file))

	return res
	    
    #
    # Update the archive from the temporary install path
    # log is a string detailing the update
    # If the profile was installed and some file are now missing they
    # will be removed from the archive.
    # If some file from the profile are not readable they will be skipped and
    # will show in the result with a 'failed' handler.
    # Returns the list of tupples (file, handler name) remaining
    # and updated in the archive
    #
    # FIXME: does this make any sense at all if its not installed ?
    #
    def update_all(self, log):
        res = []
        deleted = []
	identical = []
        modified = []
	errors = 0

        #
	# Get first the list of resources modified, identical or deleted
	#
        if self.installed:
	    for file in self.__read_filelist():
		target = self.__get_abs_filename(file)
		if os.path.exists(target):
		    try:
			olddata = self.zipfile.read(file)
                    except:
                        olddata = None
                    
                    try:
			data = open(target, "r").read()
			if not olddata or olddata != data:
			    modified.append((file, data))
			else:
			    identical.append((file, data))
		    except:
		        errors = errors + 1
			res.append((file, 'error'))
		else:
		    deleted.append(file)
		    res.append((file, 'deleted'))


        #
	# Update the local metadata
	#
        self.__update_metadata(log)
	for i in modified:
	    file = i[0];
	    self.__update_file_metadata(file, log)
	for i in identical:
	    file = i[0];
	    self.__update_file_metadata(file, None)
	for file in deleted:
	    self.__delete_file_metadata(file)

        #
	# Preserve the old package if present
	#
        if self.zipfile:
	    bak = self.filename + ".bak"
	    try:
	        self.zipfile.close()
		os.rename(self.filename, bak)
                dprint("Saved old version as %s", bak)
	    except:
	        raise ProfileStorageException("Failed to save backup as %s" %
		                              (bak))
	    try:
		self.zipfile = zipfile.ZipFile(self.filename, "w")
	    except:
		os.rename(bak, self.filename)
		raise ProfileStorageException("Failed to write file %s" %
					      self.filename)
	    try:
		self.zipfile.writestr('metadata', self.doc.serialize(format=1))
	    except:
		os.rename(bak, self.filename)
		raise ProfileStorageException("Failed to write %s metadata" %
					      self.filename)
	        
        if self.zipfile:
	    for (file, data) in identical:
		self.zipfile.writestr(file, data)
	    for (file, data) in modified:
                dprint("Updating %s", file)
		self.zipfile.writestr(file, data)
		res.append(self.__get_file_info(file))
        else:
	    if self.zipfile != None:
	        self.zipfile.close()
	    try:
		self.zipfile = zipfile.ZipFile(self.filename, "w")
	    except:
		raise ProfileStorageException("Failed to write file %s" %
					      self.filename)
	    try:
		self.zipfile.writestr('metadata', self.doc.serialize(format=1))
	    except:
		raise ProfileStorageException("Failed to write %s metadata" %
					      self.filename)
	    
	    for file in self.__read_filelist():
		target = self.__get_abs_filename(file)
		if os.path.exists(target):
		    try:
			data = open(target, "r").read()
                        dprint("Updating %s", file)
			self.zipfile.writestr(file, data)
			res.append(self.__get_file_info(file))
		    except:
			res.append(self.__get_file_info(file))
		else:
		    res.append((file, 'missing'))
        #
	# Flush and reopen if further work is needed.
	#
	self.zipfile.close()
	self.zipfile = zipfile.ZipFile(self.filename, "a")
        return res
        
def run_unit_tests():
    #
    # First test create a new config file from scratch
    #
    if os.path.exists("storage-test.zip"):
        os.remove("storage-test.zip")

    prof = ProfileStorage('storage-test.zip');
    prof.install ()
    open(prof.get_install_path() + "/config1.test", "w").write("new test file 1")
    open(prof.get_install_path() + "/config2.test", "w").write("new test file 2")
    prof.add_file('config1.test', "Foo Handler", "First config test file")
    prof.add_file('config2.test', "Bar Handler", "Second config test file")
    list = prof.update_all("first save");
    prof.uninstall()

    assert os.path.exists("storage-test.zip")

    #
    # Second test install an existing profile, modify one resource
    # and update it
    #
    prof = ProfileStorage('storage-test.zip');
    list = prof.install()

    assert os.path.exists(prof.get_install_path() + "/config1.test")
    assert os.path.exists(prof.get_install_path() + "/config2.test")

    (name, handler, description) = list[0]
    assert name == "config1.test"
    assert handler == "Foo Handler"
    assert description == "First config test file"
    
    (name, handler, description) = list[1]
    assert name == "config2.test"
    assert handler == "Bar Handler"
    assert description == "Second config test file"
    
    file = prof.get_install_path() + '/' + name
    f = open(file, "w")
    f.write(time.ctime(time.time()))
    f.close()
	    
    list = prof.update_all("first test update")
    
    (name, handler, description) = list[0]
    assert name == "config2.test"
    assert handler == "Bar Handler"
    assert description == "Second config test file"
    
    open(prof.get_install_path() + "/config3.test", "w").write("new test file 3")
    prof.add_file('config3.test', "Blaa Handler", "Third config test file")
    list = prof.update_all("second test update")
    
    (name, handler, description) = list[0]
    assert name == "config3.test"
    assert handler == "Blaa Handler"
    assert description == "Third config test file"

    prof.uninstall()
    
    os.remove("storage-test.zip")
    os.remove("storage-test.zip.bak")

if __name__ == '__main__':
    run_unit_tests()
