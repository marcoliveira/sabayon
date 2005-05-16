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
import urllib2
import urlparse
#import util
import os
import stat
import string
import libxml2
import StringIO

def dprint(fmt, *args):
    print fmt % args
#    util.debug_print (util.DEBUG_CACHE, fmt % args)

def get_home_dir():
    # return util.get_home_dir()
    return "/u/veillard"

class cacheRepository:
    """This is a remote resource cache, based on Python native urllib2
       and implementing a local cache for remote resources. It will 
       provide access to copies of the resources if unavailable and
       try to transfer only files remotely modified from the cache."""
    def __init__(self, directory = None):
        info = None
	self.directory = None
	self.catalog = None
	self.root = None
        if directory != None:
	    try:
		info = os.stat(directory)
		if (not stat.S_ISDIR(info[0])) or (info[4] != os.getuid()):
		    dprint("File %s is not a directory", directory)
		    directory = None
	    except:
		dprint("Failed to check directory %s", directory)
		try:
		    os.mkdir(directory)
		    dprint("Created directory %s", directory)
		except:
		    dprint("Failed to create directory %s", directory)
		    directory = None
	if directory == None:
	    directory = get_home_dir() + "/.profile_cache"
	    try:
		info = os.stat(directory)
		if (not stat.S_ISDIR(info[0])) or (info[4] != os.getuid()):
		    dprint("File %s is not a directory", directory)
		    try:
			import shutil
			shutil.rmtree(directory, True)
			os.mkdir(directory)
			dprint("Recreated directory %s", directory)
		    except:
		        dprint("Failed to create directory %s", directory)
			directory = None
	    except:
		dprint("Failed to check directory %s", directory)
		try:
		    os.mkdir(directory)
		    dprint("Created directory %s", directory)
		except:
		    dprint("Failed to create directory %s", directory)
		    directory = None
	if info == None:
	    self.directory = None
	    return
	else:
	    self.directory = directory
	if stat.S_IMODE(info[0]) != stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR:
	    dprint("Wrong mode for %s", directory)
	    try:
		os.chmod(directory, stat.S_IRUSR +sxstat.S_IWUSR + stat.S_IXUSR)
	    except:
	        dprint("Failed to chmod %s, ignored", directory)
		self.directory = None
		return
	if self.directory == None:
	    dprint("Running with cache deactivated")
	    return

	catalogfile = self.directory + "/catalog.xml"
	try:
	    self.catalog = libxml2.readFile(catalogfile, None,
	                                    libxml2.XML_PARSE_NOBLANKS)
	except:
	    dprint("Failed to load catalog from %s" %(catalogfile))
	    self.catalog = None

	if self.catalog != None:
	    root = self.catalog.getRootElement()
	    if not root or root.name != "catalog":
	        dprint("Discarding corrupted catalog")
		self.catalog.freeDoc ()
		self.catalog = None
	    else:
	        self.root = root

	if self.catalog == None:
	    self.catalog = libxml2.newDoc("1.0")
	    self.root = self.catalog.newChild (None, "catalog", None)
	    self.__save_catalog()

    def __URL_mapping(self, URL):
        """Function to convert an URL to a local name in the cache"""
	URL = string.replace(URL, '//', _)
	URL = string.replace(URL, '/', _)
	return URL

    def __save_catalog(self):
        """Save the on disk catalog in XML format"""
        if self.catalog != None and self.directory != None:
	    f = open(self.directory + "/catalog.xml", "w")
	    f.write(self.catalog.serialize(format = 1))
	    f.close()

    def __update_catalog(self, URL, timestamp = None):
        """Update the catalog of resources in the cache with an updated entry"""
	if self.root == None:
	    return
	modified = 0
	try:
	    child = self.root.xpathEval("/catalog/entry[@URL = '%s']" % URL)[0]
	except:
	    child = None
	if child == None:
	    child = self.root.newChild(None, "entry", None)
	    child.setProp("URL", URL)
	    if timestamp == None:
	        timestamp = ""
	    child.setProp("timestamp", timestamp)
	    modified = 1
	else:
	    if child.prop("URL") == URL:
		if timestamp != None:
		    if timestamp != child.prop("timestamp"):
			child.setProp("timestamp", timestamp)
			modified = 1
		else:
		    child.setProp("timestamp", "")
		    modified = 1
	if modified == 1:
	    self.__save_catalog()

    def __catalog_lookup(self, URL):
        """lookup an entry in the catalog, it will return a tuple of the
	   file path and the timestamp if found, None otherwise. If the
	   file is referenced in the cache but has not timestamp then it
	   will return an empty string."""
	try:
	    child = self.root.xpathEval("/catalog/entry[@URL = '%s']" % URL)[0]
	except:
	    return None
	filename = self.directory + "/" + self.__URL_mapping(URL)
	try:
	    info = os.stat(filename)
	except:
	    dprint("Local cache file for %s disapeared", URL)
	    child.unlinkNode()
	    child.freeNode()
	    return None
	return child.prop("timestamp")

    def get_resource(self, URL):
        """Get a resource from the cache. It may fetch it from the network
	   or use a local copy. It returns a Python file liek open() would.
	   If passed a filename it will accept it if absolute."""
	file = None
	try:
	    decomp = urlparse.urlparse(URL)
	    if decomp[2] == URL:
	        file = URL
	except:
	    file = URL
	if file != None:
	    if file[0] != '/':
	        return None
	    try:
	        return open(file, "r")
	    except:
	        dprint("Failed to read %s", file)
	        return None
	else:
	    filename = self.directory + "/" + self.__URL_mapping(URL)
	    timestamp = __catalog_lookup(URL)
	    last_modified = None
	    try:
	        request = urllib2.Request(URL)
		if timestamp != None and timestamp != "":
		    request.add_header('If-Modified-Since', timestamp)
            except:
	        dprint("Failed to create request for %s", URL)
	        return None
	    try:
	        opener = urllib2.build_opener()
		# TODO handle time outs there ....
		datastream = opener.open(request)
		try:
		    last_modified = datastream.headers.dict['last-modified']
		except:
		    last_modified = None
	        data = datastream.read()
		datastream.close()
	    except:
	        dprint("Resource not available or older using cache")
		try:
		    return open(filename, "r")
		except:
		    dprint("Failed to read cache file %s", filename)
		    return None
            try:
	        fd = open(filename, "w")
		fd.write(data)
		fd.close()
		self.__update_catalog(URL, last_modified)
	    except:
	        dprint("Failed to write cache file %s", filename)
	    return StringIO.StringIO(data)

	        


        


def run_unit_tests ():
    import shutil

    dir = "/tmp/cache_test"
    # shutil.rmtree(dir, True)
    cache = cacheRepository(dir)

if __name__ == "__main__":
    run_unit_tests()
