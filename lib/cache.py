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
import util
import os
import stat
import string
import libxml2
import StringIO

def dprint(fmt, *args):
    util.debug_print (util.DEBUG_CACHE, fmt % args)

def get_home_dir():
    return util.get_home_dir()

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
	# delay the directory check/creation until needed
	self.orig_directory = directory

    def __check_directory(self):
        directory = self.orig_directory
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
		    info = os.stat(directory)
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
			info = os.stat(directory)
		    except:
		        dprint("Failed to create directory %s", directory)
			directory = None
	    except:
		dprint("Failed to check directory %s", directory)
		try:
		    os.mkdir(directory)
		    dprint("Created directory %s", directory)
		    info = os.stat(directory)
		except:
		    dprint("Failed to create directory %s", directory)
		    directory = None
	if info == None:
	    dprint("Running with cache deactivated")
	    self.directory = None
	    return
	else:
	    self.directory = directory
	if stat.S_IMODE(info[0]) != stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR:
	    dprint("Wrong mode for %s", directory)
	    try:
		os.chmod(directory, stat.S_IRUSR + stat.S_IWUSR + stat.S_IXUSR)
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

	# remove empty catalogs
	if self.catalog == None or self.root == None or \
	   self.root.children == None:
	    try:
		os.unlink(self.directory + "/catalog.xml")
	    except:
	        pass

    def __URL_mapping(self, URL):
        """Function to convert an URL to a local name in the cache"""
	URL = string.replace(URL, '//', "_")
	URL = string.replace(URL, '/', "_")
	return URL

    def __save_catalog(self):
        """Save the on disk catalog in XML format"""
	# don't save an empty catalog, and remove it if empty
	if self.catalog == None or self.root == None or \
	   self.root.children == None:
	    try:
		os.unlink(self.directory + "/catalog.xml")
	    except:
	        pass
	    return
        if self.catalog != None and self.directory != None:
	    f = open(self.directory + "/catalog.xml", "w")
	    f.write(self.catalog.serialize(format = 1))
	    f.close()

    def __update_catalog(self, URL, timestamp = None):
        """Update the catalog of resources in the cache with an updated entry"""
	if URL == None:
	    return
	modified = 0

        # create the catalog if needed
	if self.catalog == None:
	    self.catalog = libxml2.newDoc("1.0")
	    self.root = self.catalog.newChild (None, "catalog", None)
	    modified = 1
	if self.root == None:
	    return

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
	if self.root == None:
	    return None
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
	   If passed a filename it will accept it if absolute.
	   The return value is an absolute path to a local file."""
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
	        return file
	    except:
	        dprint("Failed to read %s", file)
	        return None
	else:
	    self.__check_directory()
	    filename = self.directory + "/" + self.__URL_mapping(URL)
	    timestamp = self.__catalog_lookup(URL)
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
		    info = os.stat(filename)
		    return filename
		except:
		    dprint("Failed to find cache file %s", filename)
		    return None
            try:
	        fd = open(filename, "w")
		fd.write(data)
		fd.close()
		self.__update_catalog(URL, last_modified)
	    except:
	        dprint("Failed to write cache file %s", filename)
		return None
	    return filename

default_cache = None

def get_default_cache():
    global default_cache

    if default_cache == None:
        default_cache = cacheRepository()
	# now we can activate the entity loader
	libxml2.setEntityLoader(libxml2_entity_loader)

    return default_cache

# redefine libxml2 entity loader to use the default cache
def libxml2_entity_loader(URL, ID, ctxt):
    dprint("Cache entity loader called for %s '%s'", URL, ID)
    the_cache = get_default_cache()
    file = the_cache.get_resource(URL)
    try:
        fd = open(file)
	dprint("Cache entity loader resolved to %s", file)
    except:
        fd = None
    return fd

# don't report errors from libxml2 parsing
def libxml2_no_error_callback(ctx, str):
    pass

libxml2.registerErrorHandler(libxml2_no_error_callback, "")

def initialize():
    get_default_cache()
    libxml2.setEntityLoader(libxml2_entity_loader)


def run_unit_tests ():
    import BaseHTTPServer
    import SimpleHTTPServer
    import shutil
    import os
    import thread
    import time

    class test_http_handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        def do_GET(self):
	    SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

	def log_message(self, format, *args):
	    pass

    def run_http_server(www):
	os.chdir(www)
	server_address = ('', 8000)
	httpd = BaseHTTPServer.HTTPServer(server_address,test_http_handler)
	dprint("starting HTTP on %s" % (www))
	httpd.handle_request()
	dprint("stopping HTTP server")

    www = "/tmp/sabayon_http_test"
    shutil.rmtree(www, True)
    os.mkdir(www)
    open(www + "/foo", "w").write("content")
    server = thread.start_new_thread(run_http_server, (www,))

    dir = "/tmp/cache_test"
    shutil.rmtree(dir, True)
    cache = cacheRepository(dir)

    f = cache.get_resource(www + "/foo")
    assert(f != None)
    data = open(f).read()
    assert(data == "content")
    dprint("absolute local path okay")

    f = cache.get_resource("foo")
    assert(f == None)
    dprint("relative path okay")

    # give time for the HTTP server to start
    time.sleep(0.5)

    f = cache.get_resource("http://localhost:8000/foo")
    assert(f != None)
    data = open(f).read()
    assert(data == "content")
    dprint("first HTTP access okay")

    f = cache.get_resource("http://localhost:8000/foo")
    assert(f != None)
    data = open(f).read()
    assert(data == "content")
    dprint("second cached HTTP access okay")

    # shutdown the cache, restart a new instance and try to get the
    # resource
    del cache
    cache = cacheRepository(dir)

    f = cache.get_resource("http://localhost:8000/foo")
    assert(f != None)
    data = open(f).read()
    assert(data == "content")
    dprint("New cache cached HTTP access okay")

    shutil.rmtree(www, True)
    shutil.rmtree(dir, True)

if __name__ == "__main__":
    run_unit_tests()
