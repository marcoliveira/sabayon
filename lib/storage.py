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

import util

verbose = 0

def print_exception():
    print sys.exc_type, sys.exc_value

class ProfileStorageException(Exception):
    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)

class ProfileStorage:
    def __init__ (self, filename = None):
        if verbose:
	    print "init", filename
        self.exists = 0
	self.modified = 0
	self.installed = 0
	self.doc = None
	self.zipfile = None
	self.filename = filename
	self.filelist = None
	self.directory = util.get_home_dir()
        if filename != None:
	    try:
	        os.stat(filename)
		self.exists = 1
	    except:
	        pass
	    if self.exists == 1:
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
		if verbose:
		    print "New profile %s" % filename
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
        
    def __get_asb_filename(self, directory, path):
        return os.path.join(os.path.abspath(directory), path)
        
    #
    # Add an entry to the archive, set up the metadata
    # This won't write the change, use update_all() or update()
    # to commit the change to the target file.
    #
    def add_file(self, file, handler, description):
	if verbose:
	    print "add_file %s" % (file)
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
	if verbose:
	    print "delete_file(%s)" % (file)
	if file in self.filelist:
	    self.filelist.delete(file)
	    self.__delete_file_metadata(file)
	    return 0
	return -1


    #
    # Install the archive, accepts an optional directory path (otherwise
    # it will use the default directory)
    # Returns the list of tupples (absolute file path, handler name)
    #
    def install(self, directory = None):
        if directory == None:
	    directory = self.directory
	else:
	    self.directory = directory
	    
        if self.exists != 1 or self.zipfile == None:
	    raise ProfileStorageException("Cannot install package %s" %
					  self.filename)
	
	res = []
	#
	# Try to walk first though all the paths to make sure everything
	# can be installed and not half of it
	# TODO: check for filesystem space left on the device.
	#
        for file in self.__read_filelist():
	    target = self.__get_asb_filename(directory, file)
	    tardir = os.path.dirname(target)
	    if not os.path.isdir(tardir):
	        if os.path.exists(tardir):
		    raise ProfileStorageException("Cannot install %s since %s is not a directory" % (target, tardir))
		try:
		    os.makedirs(tardir)
		    if verbose:
			print "created directory %s" % tardir
		except:
		    raise ProfileStorageException("Cannot create directory %s" % (tardir))
            if os.path.exists(tardir) and not os.access(tardir, os.W_OK):
		raise ProfileStorageException("Directory %s is not writable" % (tardir))
            if os.path.exists(target) and not os.access(target, os.W_OK):
		raise ProfileStorageException("File %s is not writable" % (target))
	
	for file in self.__read_filelist():
	    target = self.__get_asb_filename(directory, file)
	    tardir = os.path.dirname(target)
	    data = self.zipfile.read(file)
	    if verbose:
		if os.path.exists(target):
		    print "Overwriting %s" % target
		else:
		    print "Creating %s" % target
	    try:
		f = open(target, "w");
		f.write(data)
		f.close()
	    except:
		raise ProfileStorageException("Failed to write to %s" % (target))
	    res.append((file, self.__get_metadata_handler(file)))
	    
	self.installed = 1
        return res     

    def get_directory(self):
        return self.directory

    #
    # Provides the list of entries in the archive along with some metadata
    # TODO: refine the metadata
    #
    def info_all(self):
        res = []
        for file in self.__read_filelist():
	    res.append((file, self.__get_metadata_handler(file)))

	return res
	    
    #
    # Update the archive, accepts an optional directory path (otherwise
    # it will use the default directory)
    # log is a string detailing the update
    # If the profile was installed and some file are now missing they
    # will be removed from the archive.
    # If some file from the profile are not readable they will be skipped and
    # will show in the result with a 'failed' handler.
    # Returns the list of tupples (file, handler name) remaining
    # and updated in the archive
    #
    def update_all(self, log, directory = None):
        if directory == None:
	    directory = self.directory

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
		target = self.__get_asb_filename(directory, file)
		if os.path.exists(target):
		    try:
			olddata = self.zipfile.read(file)
			data = open(target, "r").read()
			if olddata != data:
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
        if self.installed:
	    bak = self.filename + ".bak"
	    try:
	        self.zipfile.close()
		os.rename(self.filename, bak)
	        if verbose:
		    print "Saved old version as %s" % (bak)
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
	        
        if self.installed:
	    for (file, data) in identical:
		self.zipfile.writestr(file, data)
	    for (file, data) in modified:
		if verbose:
		    print "Updating %s" % (file)
		self.zipfile.writestr(file, data)
		res.append((file, self.__get_metadata_handler(file)))
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
		target = self.__get_asb_filename(directory, file)
		if os.path.exists(target):
		    try:
			data = open(target, "r").read()
			if verbose:
			    print "Updating %s" % (file)
			self.zipfile.writestr(file, data)
			res.append((file, self.__get_metadata_handler(file)))
		    except:
			res.append((file, 'error'))
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
    try:
        os.unlink('tst.zip');
    except:
        pass
    print "Creating new profile foo.zip"
    prof = ProfileStorage('tst.zip');
    open(util.get_home_dir() + "/config1.test", "w").write("new test file 1")
    open(util.get_home_dir() + "/config2.test", "w").write("new test file 2")
    prof.add_file('config1.test', None, "First config test file")
    prof.add_file('config2.test', None, "Second config test file")
    list = prof.update_all("first save");
    print "Added: ", list

    #
    # Second test install an existing profile, modify one resource
    # and update it
    #
    prof = ProfileStorage('tst.zip');
    print "Trying to install tst.zip"
    try:
	list = prof.install()
	print "Installed:", list
	try:
	    (name, handler) = list[0]
	    home = util.get_home_dir()
	    file = home + '/' + name
	    try:
		f = open(file, "w")
		f.write(time.ctime(time.time()))
		f.close()
		print "modified %s" % (file)
	    except:
	        print_exception()
		print "failed to modify %s" % (file)
	except:
	    pass
	    
	try:
	    print "Update tst.zip"
	    list = prof.update_all("test update")
	    print "Update list:", list
	except:
	    print_exception()
	    print "failed to update tst.zip"
    except:
        print "failed to install tst.zip"


if __name__ == '__main__':
    run_unit_tests()
