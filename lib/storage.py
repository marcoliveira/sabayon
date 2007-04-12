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
import os.path
import errno
import time
import socket
import shutil
import tempfile
import zipfile
import libxml2
import urlparse
import cache
import util
from config import *
import debuglog

def dprint (fmt, *args):
    debuglog.debug_log (False, debuglog.DEBUG_LOG_DOMAIN_STORAGE, fmt % args)

def recursive_del (path):
    if not os.path.exists (path):
        return
    
    if os.path.isdir (path):
	for file in os.listdir (path):
            subpath = os.path.join (path, file)
            recursive_del (subpath)
        os.rmdir (path)
    else:
        os.remove (path)

def copy_tree (dst_base, src_base, dst_name, src_name = None, overwrite = False):
    if src_name is None:
        src_name = dst_name
    
    try:
        dprint ("Making dir %s", os.path.join (dst_base, dst_name))
        os.mkdir (os.path.join (dst_base, dst_name))
    except OSError, err:
        if err.errno != errno.EEXIST:
            raise err

    for f in os.listdir (os.path.join (src_base, src_name)):
        src_path = os.path.join (src_base, src_name, f)

        if os.path.isdir (src_path):
            copy_tree (dst_base,
                       src_base,
                       os.path.join (dst_name, f),
                       os.path.join (src_name, f))
        else:
            dst_path = os.path.join (dst_base, dst_name, f)
            if overwrite or not os.path.exists (dst_path):
                shutil.copy2 (src_path, dst_path)

def unlink_children(node):
    children = node.children
    while children:
	  tmp = children
	  children = children.next
	  tmp.unlinkNode()
	  tmp.freeNode()

class ProfileStorageException (Exception):
    pass
        
class ProfileStorage:
    """An encapsulation of all the files which make up the
    contents of a profile.

    The files are stored in a ZIP file with metadata. In
    order to add/extract files to the profile, they are first
    copied to/from a temporary directory which is then zipped.
    Note, though, that the fact that its a ZIP file and the
    fact that there is a temporary directory are both
    implementation details and not exposed in the API.

    Profile files are stored in /etc/desktop-profiles.

    Each file or directory in the profile has metadata
    associated with it - the "source" of the file/directory
    and a set of arbitrary key value pairs which that source
    may interpret.
    """
    
    def __init__ (self, name):
        """Create a ProfileStorage.

        @name: the name of the profile - translates to
        /etc/desktop-profiles/$(name).zip.
        """
        self.name = name
	self.readonly = 0
	
        if not os.path.isabs (self.name):
	    try:
	        protocol = urlparse.urlparse(self.name)[0]
	        if protocol == "":
		    self.path = os.path.join (PROFILESDIR, self.name + ".zip")
		else:
		    # if someone uses file:/// they deserve to have troubles
		    self.readonly == 1
		    cachou = cache.get_default_cache()
		    self.path = cachou.get_resource(self.name)
		    if self.path == None:
		        self.path = self.name
		    
	    except:
		self.path = os.path.join (PROFILESDIR, self.name + ".zip")
        else:
            self.path = name
            
        self.metadata         = None
        self.zip              = None
        self.temp_path        = None
        self.needs_saving     = False

        dprint ("Creating profile '%s' from '%s'", self.name, self.path)

    def __del__ (self):
        if self.temp_path:
            shutil.rmtree (self.temp_path)
        self.temp_path = None
        
        if self.metadata:
            self.metadata.freeDoc ()
        self.metadata = None
            
        if self.zip:
            self.zip.close ()
        self.zip = None

    def __create_empty_metadata_doc (self):
        metadata = libxml2.newDoc ("1.0")
        root = metadata.newChild (None, "metadata", None)
        root.newChild (None, "directories", None)
        root.newChild (None, "files", None)
        return metadata
        
    def __read_metadata (self):
        if not self.metadata is None:
            return

        if not os.path.exists (self.path):
            dprint ("Profile file '%s' doesn't exist", self.path)
            self.metadata = self.__create_empty_metadata_doc ()
            self.needs_saving = True
            return

        dprint ("Reading metadata from '%s'", self.path)
            
        try:
            self.zip = zipfile.ZipFile (self.path, "r")
        except:
            raise ProfileStorageException (_("Failed to read file '%s': %s") %
                                           (self.path, sys.exc_info()[1]))

        try:
            blob = self.zip.read ("metadata")
            doc = libxml2.readMemory (blob, len (blob),
                                      "metadata",
                                      None,
                                      libxml2.XML_PARSE_NOBLANKS)
        except:
            raise ProfileStorageException (_("Failed to read metadata from '%s': %s") %
                                           (self.path, sys.exc_info()[1]))
        
        root = doc.getRootElement ()
        if not root or root.name != "metadata":
            doc.freeDoc ()
            raise ProfileStorageException (_("Invalid metadata section in '%s': %s") %
                                           (self.path, sys.exc_info()[1]))
            
        self.metadata = doc

        if len (root.xpathEval ("directories")) == 0:
            root.newChild (None, "directories", None)
        if len (root.xpathEval ("files")) == 0:
            root.newChild (None, "files", None)
            
    def __get_node_source (self, node):
        return node.xpathEval ("string (source)")

    def __get_node_attributes (self, node):
        attributes = {}
        for attrnode in node.xpathEval ("attributes/attribute"):
            attributes[attrnode.prop ("name")]  = attrnode.prop ("value")
        return attributes

    def __update_file_or_dir_node (self, file_or_dir_node, source, attributes, metadata):
        # Set properties

        unlink_children (file_or_dir_node)
        
        file_or_dir_node.setProp ("timestamp", str (int (time.time ())))
        file_or_dir_node.setProp ("user",      util.get_user_name ())
        file_or_dir_node.setProp ("host",      socket.gethostname ())

        # Set source and attributes
        file_or_dir_node.newChild (None, "source", source)
        
        attributes_node = file_or_dir_node.newChild (None, "attributes", None)
        if attributes:
            for name in attributes:
                attribute_node = attributes_node.newChild (None, "attribute", None)
                attribute_node.setProp ("name",  str (name))
                attribute_node.setProp ("value", str (attributes[name]))

    def __update_file_node (self, path, source, attributes, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata

        files_node = metadata.xpathEval ("/metadata/files")[0]
        
        # Ensure the file node exists
        nodes = files_node.xpathEval ("file[@path='%s']" % path)
        if len (nodes):
            file_node = nodes[0]
        else:
            file_node = files_node.newChild (None, "file", None)
            file_node.setProp ("path", path)

        self.__update_file_or_dir_node (file_node, source, attributes, metadata)

    def __update_directory_node (self, path, source, attributes, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata

        files_node = metadata.xpathEval ("/metadata/directories")[0]
        
        # Ensure the directory node exists
        nodes = files_node.xpathEval ("directory[@path='%s']" % path)
        if len (nodes):
            directory_node = nodes[0]
        else:
            directory_node = files_node.newChild (None, "directory", None)
            directory_node.setProp ("path", path)

        self.__update_file_or_dir_node (directory_node, source, attributes, metadata)

    def __unpack (self):
        self.__read_metadata ()

        if self.temp_path:
            return
        
        self.temp_path = tempfile.mkdtemp (prefix = "sabayon-profile-storage-")

        dprint ("Unpacking '%s' in '%s'", self.path, self.temp_path)

        if not self.zip:
            return
        
        def unzip_directory (zip, dir, name):
            if not os.path.exists (os.path.join (dir, name)):
                os.makedirs (os.path.join (dir, name))
            for f in zip.namelist ():
                if not f.startswith (name):
                    continue

                dest_path = os.path.join (dir, f)
                dest_dir  = os.path.dirname (dest_path)

                if not os.path.exists (dest_dir):
                    os.makedirs (dest_dir)
                
                # It sucks that we lose file permissions, mtime etc. with ZIP
                file (dest_path, "w").write (zip.read (f))
        
        def unzip_foreach (path, is_directory, data):
            (zip, temp_path) = data

            dprint ("Unzip: path = %s, is_directory = %s",
                    path, is_directory)
            
            abs_path = os.path.join (temp_path, path)
                
            if is_directory:
                unzip_directory (zip, temp_path, path)
            else:
                dest_dir = os.path.join (temp_path, os.path.dirname (path))
                if not os.path.exists (dest_dir):
                    os.makedirs (dest_dir)
                                                           
                # It sucks that we lose file permissions, mtime etc. with ZIP
                file (abs_path, "w").write (zip.read (path))

        self.__foreach_all (unzip_foreach, (self.zip, self.temp_path))

    def __foreach_all (self, callback, user_data):
        for file_node in self.metadata.xpathEval ("/metadata/files/file"):
            path = file_node.prop ("path")
            callback (path, False, user_data)
            
        for directory_node in self.metadata.xpathEval ("/metadata/directories/directory"):
            path = directory_node.prop ("path")
            callback (path, True, user_data)

    def copy (self, name):
        """Create a new ProfileStorage object, copying the
        contents of this profile to the new profile.

        @name: the name of the new profile.

        Return value: a #ProfileStorage object.
        """
        if os.path.isfile (self.path) and zipfile.is_zipfile (self.path):
            new_path = os.path.join (PROFILESDIR, name + ".zip")
            try:
                shutil.copyfile (self.path, new_path)
            except:
                dprint ("Failed to copy profile from '%s' to '%s': %s",
                        self.path, new_path, sys.exc_info()[1])
        
        retval = ProfileStorage (name)
        retval.save ()
        return retval

    def add (self, path, src_dir, source, attributes = None, src_path = None):
        """Add a new - or update an existing - file or directory
        to the profile. If @path is a directory, then the contents
        of the directory will be recursively saved in the profile.

        @path: the relative path of the file or directory.
        @src_dir: the directory (which @path is relative to) from
        which the file or directory contents should be copied to
        the profile.
        @source: the name of the #ProfileSource with which the file
        or directory is associated.
        @attributes: a varargs list of arbitrary key/value pairs
        (specific to @source) which should be saved.
        """
        dprint ("Adding '%s' from %s:%s", path, source, src_dir)
        
        self.__unpack ()

        if src_path == None:
            src_path = path
        src_path = os.path.join (src_dir, src_path)
        dst_path = os.path.join (self.temp_path, path)

        if not os.path.exists (src_path):
            raise ProfileStorageException (_("Cannot add non-existent file '%s'") % src_path)

        # Remove old version
        node = self.__get_node (path)
        if node:
            node.unlinkNode ()
            node.freeNode ()
        recursive_del (dst_path)
        
        if os.path.isdir (src_path):
            self.__update_directory_node (path, source, attributes)
            copy_tree (self.temp_path, src_dir, path)
        else:
            self.__update_file_node (path, source, attributes)
            dirname = os.path.dirname (dst_path)
            if not os.path.exists (dirname):
                os.makedirs (dirname)
            shutil.copy2 (src_path, dst_path)

        self.needs_saving = True

    def __get_dir_node (self, path, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        dir_nodes = metadata.xpathEval ("/metadata/directories/directory[@path='%s']" % path)
        if len (dir_nodes) > 0:
            return dir_nodes[0]
        return None

    def __get_file_node (self, path, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        file_nodes = metadata.xpathEval ("/metadata/files/file[@path='%s']" % path)
        if len (file_nodes) > 0:
            return file_nodes[0]
        return None

    def __get_node (self, path, metadata = None):
        self.__read_metadata ()

        node = self.__get_dir_node (path, metadata)
        if node:
            return node
        node = self.__get_file_node (path, metadata)
        if node:
            return node
        return None

    def remove (self, path):
        """Remove a file or directory from the profile.

        @path: the relative path of the file or directory. This is
        the same path used with ProfileStorage::add().
        """
        dprint ("Removing '%s' profile from profile %s", path, self.name)

        self.__unpack ()
        
        item_node = self.__get_node (path)
        if not item_node:
            return

        item_node.unlinkNode ()
        item_node.freeNode ()

        recursive_del (os.path.join (self.temp_path, path))

        self.needs_saving = True
        
    def __get_item_type (self, path):
        self.__read_metadata ()

        node = self.__get_dir_node (path)
        if node:
            return "directory"
        node = self.__get_file_node (path)
        if node:
            return "file"
        return None
        
    def get_extract_src_path (self, path):
        """Return the src path of a file or directory for extraction from the profile.

        @path: the relative path of the file or directory to extract.
        This is the same path used with ProfileStorage::add().
        """
        extract_src_path = os.path.join (self.temp_path, path)

        dprint ("Extract src path for '%s'  is '%s'", path, extract_src_path)
        
        return os.path.normpath (extract_src_path)

    def extract (self, path, dst_dir, overwrite = False):
        """Extract a file or directory from the profile.

        @path: the relative path of the file or directory to extract.
        This is the same path used with ProfileStorage::add().
        @dst_dir: the directory to which the file or directory specified
        by @path should be extracted. Any subdirectories of @dst_dir
        specified by @path will be created.
        """

        def copy_preserving_permissions (src, dest):
            # The temporary home directory may have gotten files from
            # /etc/skel which are read-only *and* which are also
            # present in the saved user profile.  Doing shutil.copy2()
            # on them would yield an exception, since they are
            # read-only in the temporary home directory.  So, first we
            # preserve the mode of those files, then delete them,
            # write new versions, and restore the mode.

            got_stat = False
            try:
                buf = os.stat (dest)
                got_stat = True
            except OSError, err:
                if err.errno != errno.ENOENT:
                    raise err

            if got_stat:
                os.unlink (dest) # FIXME: this could fail, but that would be because the parent
                                 # directory is not writable.  Then we have bigger problems, anyway.

            # FIXME: we lose the "original" permissions, mtime, etc. with ZIP files.
            shutil.copy2 (src, dest)

            if got_stat:
                os.chmod (dest, buf.st_mode)
            
        dprint ("Extracting '%s' to '%s'", path, dst_dir)
        
        self.__unpack ()

        item_type = self.__get_item_type (path)

        if item_type == "directory":
            copy_tree (dst_dir, self.temp_path, path, None, overwrite)
        else:
            dst_path = os.path.join (dst_dir, path)
            if overwrite or not os.path.exists (dst_path):
                dirname = os.path.dirname (dst_path)
                if not os.path.exists (dirname):
                    os.makedirs (dirname)

                copy_preserving_permissions (os.path.join (self.temp_path, path), dst_path)

    def list (self, source = None):
        """List the current contents of the profile.

        @source: an (optional) identifier of the source whose
        files should be listed. This is identifier as @source
        passed to ProfileStorage::add().

        Return value: a list of (@source, @path) tuples.
        """
        def listify (source, path, retval):
            retval.append ((source, path))

        retval = []
        self.foreach (listify, retval, source)

        return retval

    def __foreach_node (self, node, callback, user_data, source):
        item_path = node.prop ("path")
            
        item_source = self.__get_node_source (node)
        if not item_source:
            dprint ("No source associated with item '%s'", item_path)
            return
        
        if source and source != item_source:
            return
        
        if not user_data is None:
            callback (item_source, item_path, user_data)
        else:
            callback (item_source, item_path)

    def foreach (self, callback, user_data = None, source = None):
        """Iterate over the contents of the profile:

        @callback: an function or method of which takes 
        at least two arguments - @source and @path. If @callback
        is a method, the object which the method is associated
        will be the first parameter. If @user_data is passed,
        then it will be the final parameter to the callback.
        @user_data: an (optional) parameter to pass to @callback.
        @source: an (optional) identifier of the source whose
        files should be listed.
        """
        self.__read_metadata ()

        for node in self.metadata.xpathEval ("/metadata/files/file"):
            self.__foreach_node (node, callback, user_data, source)
            
        for node in self.metadata.xpathEval ("/metadata/directories/directory"):
            self.__foreach_node (node, callback, user_data, source)

    def save (self):
        """Save the contents of the profile to
        /etc/desktop-profiles/$(name).zip.
        """
	if self.readonly:
            raise ProfileStorageException (_("Profile is read-only %s") %
                                           (self.name))
        self.__read_metadata ()
        if not self.needs_saving:
            dprint ("No changes to profile '%s' need saving", self.name)
            return

        def failsafe_rename (src, dst):
            try:
                os.rename (src, dst)
            except:
                pass

        if os.path.exists (self.path):
            backup = self.path + ".bak"
            failsafe_rename (self.path, backup)
        else:
            backup = None
        
        dprint ("Writing contents of profile to '%s'", self.path)
        
        try:
            save_zip = zipfile.ZipFile (self.path, "w")

            save_zip.writestr ("metadata", self.metadata.serialize (format = 1))

            def zip_directory (save_zip, dir, name):
                for f in os.listdir (dir):
                    path = os.path.join (dir, f)
                    if os.path.isdir (path):
                        zip_directory (save_zip,
                                       path,
                                       os.path.join (name, f))
                    elif os.path.isfile (path):
                        save_zip.write (path, os.path.join (name, f))
        
            def zip_foreach (path, is_directory, data):
                (save_zip, temp_path) = data

                abs_path = os.path.join (temp_path, path)
                    
                if is_directory:
                    zip_directory (save_zip, abs_path, path)
                else:
                    save_zip.write (abs_path, path)

            self.__foreach_all (zip_foreach, (save_zip, self.temp_path))

            save_zip.close ()
        except:
            if backup:
                failsafe_rename (backup, self.path)
            raise

        if backup:
            os.remove (backup)

        if self.temp_path:
            shutil.rmtree (self.temp_path)
            self.temp_path = None
        
        self.needs_saving = False
        
        self.zip = zipfile.ZipFile (self.path, "r")

    def get_attributes (self, path):
        """Return the attributes associated with a file or directory
        from the profile.

        @path: the relative path of the file or directory to look up.
        This is the same path used with ProfileStorage::add().

        Return value: a dictionary containing the key/value pairs
        passed to ProfileStorage::add().
        """
        node = self.__get_node (path)
        if node is None:
            return {}
        return self.__get_node_attributes (node)

    def get_source (self, path):
        """Return the source associated with a file or directory
        from the profile.

        @path: the relative path of the file or directory to look up.
        This is the same path used with ProfileStorage::add().

        Return value: a source identifier.
        """
        node = self.__get_node (path)
        if node is None:
            return None
        return self.__get_node_source (node)

#
# Unit tests
#
def run_unit_tests ():
    # Remove cruft
    profile_path = os.path.join (os.getcwd (), "storage-test.zip")
    if os.path.exists (profile_path):
        os.remove (profile_path)

    # Create temporary dir for test
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")

    # Create profile
    profile = ProfileStorage (profile_path)
    
    # Save the profile (no revision yet)
    profile.save ()
    assert os.path.exists (profile_path)

    # Create two test files in the temporary dir
    os.mkdir (os.path.join (temp_dir, "t"))
    open (os.path.join (temp_dir, "t/config1.test"), "w").write ("new test file 1")
    open (os.path.join (temp_dir, "config2.test"), "w").write ("new test file 2")

    # Add the two test files to the profile
    profile.add ("t/config1.test", temp_dir, "TestSource1", { "foo-attr1" : "foo" , "bar-attr1" : 1 })
    profile.add ("config2.test", temp_dir, "TestSource2", { "foo-attr2" : "foo" , "bar-attr2" : 2 })

    # Create a test directory with some files
    os.makedirs (os.path.join (temp_dir, "foobar/foo/bar/foo/bar"))
    open (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml"), "w").write ("new test file 3")
    open (os.path.join (temp_dir, "foobar/foo/bar/foo.txt"), "w").write ("new test file 4")
    open (os.path.join (temp_dir, "foobar/foo/bar.txt"), "w").write ("new test file 5")
    open (os.path.join (temp_dir, "foobar/foo.txt"), "w").write ("new test file 6")

    # Add the test directory to the profile
    profile.add ("foobar", temp_dir, "TestSource3", { "foo-attr3" : "foo" , "bar-attr3" : 3 })
    
    # Save the profile (first revision)
    profile.save ()
    assert os.path.exists (profile_path)

    ########## Verify the first revision
    test_profile = ProfileStorage (profile_path)
    l = test_profile.list ()
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource1"
    assert path == "t/config1.test"
    assert test_profile.get_source (path) == "TestSource1"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr1")
    assert attributes["foo-attr1"] == "foo"
    assert attributes.has_key ("bar-attr1")
    assert attributes["bar-attr1"] == "1"
    
    (source, path) = l[1]
    assert source == "TestSource2"
    assert path == "config2.test"
    assert test_profile.get_source (path) == "TestSource2"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2")
    assert attributes["foo-attr2"] == "foo"
    assert attributes.has_key ("bar-attr2")
    assert attributes["bar-attr2"] == "2"
    
    (source, path) = l[2]
    assert source == "TestSource3"
    assert path == "foobar"
    assert test_profile.get_source (path) == "TestSource3"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr3")
    assert attributes["foo-attr3"] == "foo"
    assert attributes.has_key ("bar-attr3")
    assert attributes["bar-attr3"] == "3"

    # Create temporary dir for extraction
    temp_dir2 = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        test_profile.extract (path, temp_dir2)

    # Verify their contents
    assert os.path.isfile (os.path.join (temp_dir2, "t/config1.test"))
    assert file (os.path.join (temp_dir2, "t/config1.test")).read () == "new test file 1"
    assert os.path.isfile (os.path.join (temp_dir2, "config2.test"))
    assert file (os.path.join (temp_dir2, "config2.test")).read () == "new test file 2"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo/bar/foo/bar/%gconf.xml"))
    assert file (os.path.join (temp_dir2, "foobar/foo/bar/foo/bar/%gconf.xml")).read () == "new test file 3"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo/bar/foo.txt"))
    assert file (os.path.join (temp_dir2, "foobar/foo/bar/foo.txt")).read () == "new test file 4"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo/bar.txt"))
    assert file (os.path.join (temp_dir2, "foobar/foo/bar.txt")).read () == "new test file 5"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo.txt"))
    assert file (os.path.join (temp_dir2, "foobar/foo.txt")).read () == "new test file 6"
    
    # Remove temporary extraction dir
    shutil.rmtree (temp_dir2)

    ########## Create second revision

    # Add one of the test files again to get a new revision
    open (os.path.join (temp_dir, "t/config1.test"), "w").write ("new test file 99")
    profile.add ("t/config1.test", temp_dir, "TestSource99", { "foo-attr99" : "foo" , "bar-attr99" : 99 })

    # Remove one of the test files
    profile.remove ("config2.test")
    
    # Add the test directory again to get a new revision
    open (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml"), "w").write ("new test file 2005")
    open (os.path.join (temp_dir, "foobar/foo/bar/foo.txt"), "w").write ("new test file 2005")
    open (os.path.join (temp_dir, "foobar/foo/bar.txt"), "w").write ("new test file 2005")
    open (os.path.join (temp_dir, "foobar/foo.txt"), "w").write ("new test file 2005")
    profile.add ("foobar", temp_dir, "TestSource2005", { "foo-attr2005" : "foo" , "bar-attr2005" : 2005 })

    # Add another directory
    os.makedirs (os.path.join (temp_dir, "blaas/are/nice"))
    open (os.path.join (temp_dir, "blaas/are/nice/foo.txt"), "w").write ("blaas are nice")
    profile.add ("blaas", temp_dir, "Waterford", { "nice" : True, "with-butter" : "but of course" })
    
    # Remove temporary dir
    shutil.rmtree (temp_dir)

    # Save the profile (second revision)
    os.remove (profile_path)
    profile.save ()
    assert os.path.exists (profile_path)

    ########## Verify the second revision

    test_profile = ProfileStorage (profile_path)
    l = test_profile.list ()
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource99"
    assert path == "t/config1.test"
    assert test_profile.get_source (path) == "TestSource99"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr99")
    assert attributes["foo-attr99"] == "foo"
    assert attributes.has_key ("bar-attr99")
    assert attributes["bar-attr99"] == "99"

    (source, path) = l[1]
    assert source == "TestSource2005"
    assert path == "foobar"
    assert test_profile.get_source (path) == "TestSource2005"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2005")
    assert attributes["foo-attr2005"] == "foo"
    assert attributes.has_key ("bar-attr2005")
    assert attributes["bar-attr2005"] == "2005"
    
    (source, path) = l[2]
    assert source == "Waterford"
    assert path == "blaas"
    assert test_profile.get_source (path) == "Waterford"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("with-butter")
    assert attributes["with-butter"] == "but of course"
    assert attributes.has_key ("nice")
    assert attributes["nice"] == "True"

    # Create temporary dir for extraction
    temp_dir2 = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        test_profile.extract (path, temp_dir2)

    # Verify their contents
    assert os.path.isfile (os.path.join (temp_dir2, "t/config1.test"))
    assert file (os.path.join (temp_dir2, "t/config1.test")).read () == "new test file 99"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo/bar/foo/bar/%gconf.xml"))
    assert file (os.path.join (temp_dir2, "foobar/foo/bar/foo/bar/%gconf.xml")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo/bar/foo.txt"))
    assert file (os.path.join (temp_dir2, "foobar/foo/bar/foo.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo/bar.txt"))
    assert file (os.path.join (temp_dir2, "foobar/foo/bar.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir2, "foobar/foo.txt"))
    assert file (os.path.join (temp_dir2, "foobar/foo.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir2, "blaas/are/nice/foo.txt"))
    assert file (os.path.join (temp_dir2, "blaas/are/nice/foo.txt")).read () == "blaas are nice"
    
    # Remove temporary extraction dir
    shutil.rmtree (temp_dir2)

    ########## Create third revision

    # Create temporary dir again
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")
    
    # Now, re-open
    profile = ProfileStorage (profile_path)

    # Remove a directory
    profile.remove ("blaas")

    # Re-add one of the files
    open (os.path.join (temp_dir, "config2.test"), "w").write ("I'm back, yes its me!")
    profile.add ("config2.test", temp_dir, "TestSource2")

    # Save the profile (third revision)
    os.remove (profile_path)
    profile.save ()
    assert os.path.exists (profile_path)

    # Remove temp dir again
    shutil.rmtree (temp_dir)

    ########## Verify the third revision

    test_profile = ProfileStorage (profile_path)

    # Verify the last write
    l = test_profile.list ()
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource99"
    assert path == "t/config1.test"
    assert test_profile.get_source (path) == "TestSource99"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr99")
    assert attributes["foo-attr99"] == "foo"
    assert attributes.has_key ("bar-attr99")
    assert attributes["bar-attr99"] == "99"

    (source, path) = l[1]
    assert source == "TestSource2"
    assert path == "config2.test"
    assert test_profile.get_source (path) == "TestSource2"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 0

    (source, path) = l[2]
    assert source == "TestSource2005"
    assert path == "foobar"
    assert test_profile.get_source (path) == "TestSource2005"
    attributes = test_profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2005")
    assert attributes["foo-attr2005"] == "foo"
    assert attributes.has_key ("bar-attr2005")
    assert attributes["bar-attr2005"] == "2005"
    
    # Create temporary dir for extraction
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        test_profile.extract (path, temp_dir)

    # Verify their contents
    assert os.path.isfile (os.path.join (temp_dir, "t/config1.test"))
    assert file (os.path.join (temp_dir, "t/config1.test")).read () == "new test file 99"
    assert os.path.isfile (os.path.join (temp_dir, "config2.test"))
    assert file (os.path.join (temp_dir, "config2.test")).read () == "I'm back, yes its me!"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar/foo.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar/foo.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo.txt")).read () == "new test file 2005"
    
    # Remove temporary extraction dir
    shutil.rmtree (temp_dir)

    os.remove (profile_path)
