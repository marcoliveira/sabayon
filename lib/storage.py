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

def dprint (fmt, *args):
    util.debug_print (util.DEBUG_STORAGE, fmt % args)

def copy_tree (dst_base, src_base, dst_name, src_name = None, overwrite = False):
    if src_name is None:
        src_name = dst_name
    
    try:
        dprint ("Making dir %s" % os.path.join (dst_base, dst_name))
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

    The profile also contains a revision history, allowing
    you to revert to a previous version of a given file
    or a previous version of the profile itself.
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
        self.revisions_path   = None
        self.unsaved_revision = None
        self.needs_saving     = False

        dprint ("Creating profile '%s' from '%s'", self.name, self.path)

    def __del__ (self):
        if self.temp_path:
            shutil.rmtree (self.temp_path)
        self.temp_path = None
        self.revisions_path = None
        
        if self.metadata:
            self.metadata.freeDoc ()
        self.metadata = None
            
        if self.zip:
            self.zip.close ()
        self.zip = None

    def __create_empty_metadata_doc (self):
        metadata = libxml2.newDoc ("1.0")
        root = metadata.newChild (None, "metadata", None)
        root.newChild (None, "profile_revisions", None)
        root.newChild (None, "directories", None)
        root.newChild (None, "files", None)
        return metadata
        
    def __read_metadata (self):
        if not self.metadata is None:
            return

        if not os.path.exists (self.path):
            dprint ("Profile file '%s' doesn't exist" % self.path)
            self.metadata = self.__create_empty_metadata_doc ()
            self.needs_saving = True
            return

        dprint ("Reading metadata from '%s'" % self.path)
            
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

        if len (root.xpathEval ("profile_revisions")) == 0:
            root.newChild (None, "profile_revisions", None)
        if len (root.xpathEval ("directories")) == 0:
            root.newChild (None, "directories", None)
        if len (root.xpathEval ("files")) == 0:
            root.newChild (None, "files", None)

    def __get_profile_revisions (self, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        revisions = []
        for profile_revision in metadata.xpathEval ("/metadata/profile_revisions/profile_revision"):
            revisions.append ((profile_revision.prop ("id"),
                               profile_revision.prop ("timestamp")))
        return revisions
    
    def __get_current_profile_revision (self, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        return metadata.xpathEval ("string(/metadata/profile_revisions/@current)")

    def __get_profile_revision_node (self, profile_revision, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        nodes = metadata.xpathEval ("/metadata/profile_revisions/profile_revision[@id='%s']" % profile_revision)
        if not len (nodes):
            return None
        return nodes[0]

    def __get_profile_revision_item (self, revision, path, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        nodes = metadata.xpathEval ("/metadata/profile_revisions/profile_revision[@id='%s']/item[@path='%s']" %
                                    (revision, path))
        if not len (nodes):
            return None
        return nodes[0]
    
    def __get_profile_revision_items (self, revision, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        return metadata.xpathEval ("/metadata/profile_revisions/profile_revision[@id='%s']/item" % revision)

    def __get_file_revision_node (self, path, revision, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        nodes = metadata.xpathEval ("/metadata/files/file[@path='%s']/revisions/revision[@id='%s']" %
                                    (path, revision))
        if not len (nodes):
            return None
        return nodes[0]
    
    def __get_directory_revision_node (self, path, revision, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        nodes = metadata.xpathEval ("/metadata/directories/directory[@path='%s']/revisions/revision[@id='%s']" %
                                    (path, revision))
        if not len (nodes):
            return None
        return nodes[0]

    def __get_file_revisions (self, path, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        revisions = []
        for revision in metadata.xpathEval ("/metadata/files/file[@path='%s']/revisions/revision" % path):
            revisions.append ((revision.prop ("id"),
                               revision.prop ("timestamp")))
        return revisions
    
    def __get_directory_revisions (self, path, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata
        revisions = []
        for revision in metadata.xpathEval ("/metadata/directories/directory[@path='%s']/revisions/revision" % path):
            revisions.append ((revision.prop ("id"),
                               revision.prop ("timestamp")))
        return revisions

    def __get_revision_source (self, revision_node):
        return revision_node.xpathEval ("string (source)")

    def __get_revision_attributes (self, revision_node):
        attributes = {}
        for node in revision_node.xpathEval ("attributes/attribute"):
            attributes[node.prop ("name")]  = node.prop ("value")
        return attributes

    def __create_new_profile_revision (self, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata

        profile_revisions = metadata.xpathEval ("/metadata/profile_revisions")[0]
        
        current_revision = self.__get_current_profile_revision (metadata)
        if current_revision:
            current_node = self.__get_profile_revision_node (current_revision, metadata)
            new_revision = str (int (current_revision) + 1)
        else:
            current_node = None
            new_revision = "1"
            
        if current_node:
            revision_node = current_node.copyNode (extended = 1)
            current_node.addPrevSibling (revision_node)
        else:
            revision_node = profile_revisions.newChild (None, "profile_revision", None)
            
        revision_node.setProp ("id",        new_revision)
        revision_node.setProp ("timestamp", str (int (time.time ())))
        revision_node.setProp ("user",      util.get_user_name ())
        revision_node.setProp ("host",      socket.gethostname ())

        profile_revisions.setProp ("current", new_revision)

        return new_revision

    def __create_new_file_or_dir_revision (self, file_or_dir_node, source, attributes, metadata):
        # Ensure the revisions node exists
        nodes = file_or_dir_node.xpathEval ("revisions")
        if len (nodes):
            revisions_node = nodes[0]
        else:
            revisions_node = file_or_dir_node.newChild (None, "revisions", None)

        # Find a new revision id
        old_revision_id = 0
        for node in revisions_node.xpathEval ("revision"):
            i = int (node.prop ("id"))
            if i > old_revision_id:
                old_revision_id = i
        revision_id = str (old_revision_id + 1)
        if old_revision_id:
            old_revision_id = str (old_revision_id)
        else:
            old_revision_id = None

        # Create a new revision node
        if revisions_node.children:
            revision_node = metadata.newDocNode (None, "revision", None)
            revisions_node.children.addPrevSibling (revision_node)
        else:
            revision_node = revisions_node.newChild (None, "revision", None)

        # Set properties
        revision_node.setProp ("id",        revision_id)
        revision_node.setProp ("timestamp", str (int (time.time ())))
        revision_node.setProp ("user",      util.get_user_name ())
        revision_node.setProp ("host",      socket.gethostname ())

        # Set source and attributes
        revision_node.newChild (None, "source", source)
        
        attributes_node = revision_node.newChild (None, "attributes", None)
        if attributes:
            for name in attributes:
                attribute_node = attributes_node.newChild (None, "attribute", None)
                attribute_node.setProp ("name",  str (name))
                attribute_node.setProp ("value", str (attributes[name]))

        return (revision_id, old_revision_id)

    def __create_new_file_revision (self, path, source, attributes, metadata = None):
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

        return self.__create_new_file_or_dir_revision (file_node, source, attributes, metadata)

    def __create_new_directory_revision (self, path, source, attributes, metadata = None):
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

        return self.__create_new_file_or_dir_revision (directory_node, source, attributes, metadata)

    def __add_profile_revision_item (self, profile_revision, path, type, revision, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata

        profile_revision_node = metadata.xpathEval ("/metadata/profile_revisions/profile_revision[@id='%s']" %
                                                    profile_revision)[0]

        nodes = profile_revision_node.xpathEval ("item[@path='%s']" % path)
        if len (nodes):
            item_node = nodes[0]
        else:
            item_node = profile_revision_node.newChild (None, "item", None)
            item_node.setProp ("path", path)

        item_node.setProp ("type", type)
        item_node.setProp ("revision", revision)

    def __item_revision_is_current (self, path, type, revision, metadata = None):
        if metadata is None:
            metadata = self.metadata
        assert metadata

        current_profile_revision = self.__get_current_profile_revision (metadata)
        if not current_profile_revision:
            return False

        return metadata.xpathEval ("boolean(/metadata/profile_revisions/profile_revision[@id='%s']"
                                   "/item[@path='%s' and @type='%s' and @revision='%s'])" %
                                   (current_profile_revision, path, type, revision))
        
    def __unpack (self):
        self.__read_metadata ()

        if self.temp_path:
            return
        
        self.temp_path = tempfile.mkdtemp (prefix = "sabayon-profile-storage-")
        self.revisions_path = os.path.join (self.temp_path, "%revisions%")
        os.mkdir (self.revisions_path)

        dprint ("Unpacking '%s' in '%s'" % (self.path, self.temp_path))

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
        
        def unzip_foreach (path, revision, is_current, is_directory, data):
            (zip, temp_path, revisions_path) = data

            dprint ("Unzip: path = %s, revision = %s, is_current = %s, is_directory = %s",
                    path, revision, is_current, is_directory)
            
            if is_current:
                abs_path = os.path.join (temp_path, path)
            else:
                abs_path = os.path.join (revisions_path, path, revision)
                path = os.path.join ("%revisions%", path, revision)
                
            if is_directory:
                unzip_directory (zip, temp_path, path)
            else:
                dest_dir = os.path.join (temp_path, os.path.dirname (path))
                if not os.path.exists (dest_dir):
                    os.makedirs (dest_dir)
                                                           
                # It sucks that we lose file permissions, mtime etc. with ZIP
                file (abs_path, "w").write (zip.read (path))

        self.__foreach_all (unzip_foreach, (self.zip, self.temp_path, self.revisions_path))

    def __foreach_revision (self, node, type, callback, user_data):
        path = node.prop ("path")
        for revision in node.xpathEval ("revisions/revision"):
            revision_id = revision.prop ("id")
            callback (path,
                      revision_id,
                      self.__item_revision_is_current (path, type, revision_id),
                      type == "directory",
                      user_data)

    def __foreach_all (self, callback, user_data):
        for file_node in self.metadata.xpathEval ("/metadata/files/file"):
            self.__foreach_revision (file_node, "file", callback, user_data)
        for directory_node in self.metadata.xpathEval ("/metadata/directories/directory"):
            self.__foreach_revision (directory_node, "directory", callback, user_data)

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
                dprint ("Failed to copy profile from '%s' to '%s': %s" % \
                        (self.path, new_path, sys.exc_info()[1]))
        
        retval = ProfileStorage (name)
        retval.clear_revisions ()
        retval.save ()
        return retval

    def add (self, path, src_dir, source, attributes = None):
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
        dprint ("Adding '%s' from %s:%s" % (path, source, src_dir))
        
        self.__unpack ()

        src_path = os.path.join (src_dir, path)
        dst_path = os.path.join (self.temp_path, path)

        if not os.path.exists (src_path):
            raise ProfileStorageException (_("Cannot add non-existent file '%s'") % src_path)
        
        if not self.unsaved_revision:
            self.unsaved_revision = self.__create_new_profile_revision ()
            
        if os.path.isdir (src_path):
            (new_revision, old_revision) = self.__create_new_directory_revision (path, source, attributes)
            if old_revision:
                needs_copying = self.__item_revision_is_current (path, "directory", old_revision)
            else:
                needs_copying = False
            self.__add_profile_revision_item (self.unsaved_revision, path, "directory", new_revision)

            if needs_copying:
                revision_path = os.path.join (self.revisions_path, path, old_revision)
                dprint ("Retaining old revision of '%s' from '%s' to '%s'",
                        path, dst_path, revision_path)
                os.renames (dst_path, revision_path)
            
            copy_tree (self.temp_path, src_dir, path)
        else:
            (new_revision, old_revision) = self.__create_new_file_revision (path, source, attributes)
            if old_revision:
                needs_copying = self.__item_revision_is_current (path, "file", old_revision)
            else:
                needs_copying = False
            self.__add_profile_revision_item (self.unsaved_revision, path, "file", new_revision)
            
            if needs_copying:
                revision_path = os.path.join (self.revisions_path, path, old_revision)
                dprint ("Retaining old revision of '%s' from '%s' to '%s'",
                        path, dst_path, revision_path)
                os.renames (dst_path, revision_path)

            dirname = os.path.dirname (dst_path)
            if not os.path.exists (dirname):
                os.makedirs (dirname)
            shutil.copy2 (src_path, dst_path)

        self.needs_saving = True

    def remove (self, path):
        """Remove a file or directory from the profile.

        @path: the relative path of the file or directory. This is
        the same path used with ProfileStorage::add().
        """
        dprint ("Removing '%s' profile from profile %s", path, self.name)

        self.__unpack ()
        
        if not self.unsaved_revision:
            self.unsaved_revision = self.__create_new_profile_revision ()

        item_node = self.__get_profile_revision_item (self.unsaved_revision, path)
        if not item_node:
            return

        item_type     = item_node.prop ("type")
        item_revision = item_node.prop ("revision")

        item_node.unlinkNode ()
        item_node.freeNode ()
        
        os.renames (os.path.join (self.temp_path, path),
                    os.path.join (self.revisions_path, path, item_revision))

        self.needs_saving = True
        
    def extract (self, path, dst_dir, overwrite = False, revision = None):
        """Extract a file or directory from the profile.

        @path: the relative path of the file or directory to extract.
        This is the same path used with ProfileStorage::add().
        @dst_dir: the directory to which the file or directory specified
        by @path should be extracted. Any subdirectories of @dst_dir
        specified by @path will be created.
        @revision: an (optional) revision identifier which specifies
        the revision of the file or directory which should be extracted.
        The revision identifier must have been returned from
        ProfileStorage::get_revisions() and may be a profile or file
        revision.
        """
        dprint ("Extracting '%s' to '%s', revision %s" % (path, dst_dir, revision))
        
        self.__unpack ()

        if not revision:
            profile_revision = self.__get_current_profile_revision ()
            if not profile_revision:
                raise ProfileStorageException (_("No current revision"))
            
            item = self.__get_profile_revision_item (profile_revision, path)
            if not item:
                raise ProfileStorageException (_("'%s' does not exist in profile revision '%s'"),
                                               path, profile_revision)

            item_type     = item.prop ("type")
            item_revision = item.prop ("revision")
        else:
            (item_type, item_revision) = revision.split (":")

            if item_type == "profile":
                item = self.__get_profile_revision_item (item_revision, path)
                if not item:
                    raise ProfileStorageException (_("'%s' does not exist in profile revision '%s'"),
                                                   path, profile_revision)
                    return

                item_type     = item.prop ("type")
                item_revision = item.prop ("revision")

        if self.__item_revision_is_current (path, item_type, item_revision):
            if item_type == "directory":
                copy_tree (dst_dir, self.temp_path, path, None, overwrite)
            else:
                dst_path = os.path.join (dst_dir, path)
                if overwrite or not os.path.exists (dst_path):
                    dirname = os.path.dirname (dst_path)
                    if not os.path.exists (dirname):
                        os.makedirs (dirname)
                    shutil.copy2 (os.path.join (self.temp_path, path), dst_path)
        else:
            if item_type == "directory":
                copy_tree (dst_dir,
                           os.path.join (self.revisions_path, path),
                           path,
                           item_revision,
                           overwrite)
            else:
                dst_path = os.path.join (dst_dir, path)
                if overwrite or not os.path.exists (dst_path):
                    dirname = os.path.dirname (dst_path)
                    if not os.path.exists (dirname):
                        os.makedirs (dirname)
                    shutil.copy2 (os.path.join (self.revisions_path, path, item_revision), dst_path)

    def list (self, source = None, profile_revision = None):
        """List the current contents of the profile.

        @source: an (optional) identifier of the source whose
        files should be listed. This is identifier as @source
        passed to ProfileStorage::add().
        @profile_revision: specify the profile revision whose contents
        should be listed. Defaults to the current revision.

        Return value: a list of (@source, @path) tuples.
        """
        def listify (source, path, retval):
            retval.append ((source, path))

        retval = []
        self.foreach (listify, retval, source, profile_revision)

        return retval

    def foreach (self, callback, user_data = None, source = None, profile_revision = None):
        """Iterate over the contents of the profile:

        @callback: an function or method of which takes 
        at least two arguments - @source and @path. If @callback
        is a method, the object which the method is associated
        will be the first parameter. If @user_data is passed,
        then it will be the final parameter to the callback.
        @user_data: an (optional) parameter to pass to @callback.
        @source: an (optional) identifier of the source whose
        files should be listed.
        @profile_revision: an (optional) profile revision from
        which the files should be listed. Defaults to the current
        revision.
        """
        self.__read_metadata ()

        if not profile_revision:
            profile_revision = self.__get_current_profile_revision ()
        else:
            if not profile_revision.startswith ("profile:"):
                raise ProfileStorageException (_("Not a valid profile revision"))
            profile_revision = profile_revision[len ("profile:"):]
        
        if not profile_revision:
            return

        for item in self.__get_profile_revision_items (profile_revision):
            item_path     = item.prop ("path")
            item_type     = item.prop ("type")
            item_revision = item.prop ("revision")

            if item_type == "file":
                revision_node = self.__get_file_revision_node (item_path, item_revision)
            elif item_type == "directory":
                revision_node = self.__get_directory_revision_node (item_path, item_revision)
            else:
                dprint ("Unknown item type '%s' for path '%s' in revision '%s'" %
                        (item_type, item_path, item_revision))
                continue

            if not revision_node:
                dprint ("No revision '%s' for %s '%s" % (item_revision, item_type, item_path))
                continue

            item_source = self.__get_revision_source (revision_node)
            if not item_source:
                dprint ("No source associated with item '%s'" % item_path)
                continue

            if source and source != item_source:
                continue

            if not user_data is None:
                callback (item_source, item_path, user_data)
            else:
                callback (item_source, item_path)

    def save (self):
        """Save the contents of the profile to
        /etc/desktop-profiles/$(name).zip.
        """
	if self.readonly:
            raise ProfileStorageException (_("Profile is read-only %s") %
                                           (self.name))
        self.__read_metadata ()
        if not self.needs_saving:
            dprint ("No changes to profile '%s' need saving" % self.name)
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
        
        dprint ("Writing contents of profile to '%s'" % self.path)
        
        try:
            save_zip = zipfile.ZipFile (self.path, "w")

            save_zip.writestr ("metadata", self.metadata.serialize (format = 1))
            self.unsaved_revision = None

            def zip_directory (save_zip, dir, name):
                for f in os.listdir (dir):
                    path = os.path.join (dir, f)
                    if os.path.isdir (path):
                        zip_directory (save_zip,
                                       path,
                                       os.path.join (name, f))
                    elif os.path.isfile (path):
                        save_zip.write (path, os.path.join (name, f))
        
            def zip_foreach (path, revision, is_current, is_directory, data):
                (save_zip, temp_path, revisions_path) = data

                if is_current:
                    abs_path = os.path.join (temp_path, path)
                else:
                    abs_path = os.path.join (revisions_path, path, revision)
                    path = os.path.join ("%revisions%", path, revision)
                    
                if is_directory:
                    zip_directory (save_zip, abs_path, path)
                else:
                    save_zip.write (abs_path, path)

            self.__foreach_all (zip_foreach, (save_zip, self.temp_path, self.revisions_path))

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
            self.revisions_path = None
        
        self.needs_saving = False
        
        self.zip = zipfile.ZipFile (self.path, "r")

    def __get_revision_node (self, path, revision):
        self.__read_metadata ()

        if not revision:
            profile_revision = self.__get_current_profile_revision ()
            if not profile_revision:
                return None
            
            item = self.__get_profile_revision_item (profile_revision, path)
            if not item:
                return None

            item_type     = item.prop ("type")
            item_revision = item.prop ("revision")
        else:
            (item_type, item_revision) = revision.split (":")

            if item_type == "profile":
                item = self.__get_profile_revision_item (item_revision, path)
                if not item:
                    return None

                item_type     = item.prop ("type")
                item_revision = item.prop ("revision")

        if item_type == "file":
            return self.__get_file_revision_node (path, item_revision)
        elif item_type == "directory":
            return self.__get_directory_revision_node (path, item_revision)

        return None

    def get_attributes (self, path, revision = None):
        """Return the attributes associated with a file or directory
        from the profile.

        @path: the relative path of the file or directory to look up.
        This is the same path used with ProfileStorage::add().
        @revision: the profile or file/directory revision identifier
        with which to look up.

        Return value: a dictionary containing the key/value pairs
        passed to ProfileStorage::add().
        """
        revision_node = self.__get_revision_node (path, revision)
        if revision_node is None:
            return {}
        return self.__get_revision_attributes (revision_node)

    def get_source (self, path, revision = None):
        """Return the source associated with a file or directory
        from the profile.

        @path: the relative path of the file or directory to look up.
        This is the same path used with ProfileStorage::add().
        @revision: the profile or file/directory revision identifier
        with which to look up.

        Return value: a source identifier.
        """
        revision_node = self.__get_revision_node (path, revision)
        if revision_node is None:
            return None
        return self.__get_revision_source (revision_node)

    def get_revisions (self, path = None):
        """Retrieve the list of profile revisions or the list of
        revisions of a given file or directory.
        
        @path: the relative path of the file or directory to look up.
        This is the same path used with ProfileStorage::add().

        Return value: a list of revision identifiers and timestamps
        for the profile or file/directory in chronological order.
        """
        self.__read_metadata ()

        revisions = []
        if not path:
            for (revision, timestamp) in self.__get_profile_revisions ():
                revisions.append (("profile:%s" % revision, timestamp))
        else:
            for (revision, timestamp) in self.__get_file_revisions (path):
                revisions.append (("file:%s" % revision, timestamp))
            for (revision, timestamp) in self.__get_directory_revisions (path):
                revisions.append (("directory:%s" % revision, timestamp))

        return revisions

    def __copy_to_new_metadata_foreach (self, source, path, data):
        (metadata, unsaved_revision) = data
        
        attributes = self.get_attributes (path)

        if os.path.isdir (os.path.join (self.temp_path, path)):
            (new_revision, old_revision) = self.__create_new_directory_revision (path, source, attributes, metadata)
            assert not old_revision
            self.__add_profile_revision_item (unsaved_revision, path, "directory", new_revision, metadata)
        else:
            (new_revision, old_revision) = self.__create_new_file_revision (path, source, attributes, metadata)
            assert not old_revision
            self.__add_profile_revision_item (unsaved_revision, path, "file", new_revision, metadata)
        
    def clear_revisions (self):
        """Remove all profile and file/directory revision history."""
        dprint ("Clearing revision history from profile '%s'", self.name)

        self.__unpack ()

        metadata = self.__create_empty_metadata_doc ()
        unsaved_revision = self.__create_new_profile_revision (metadata)

        self.foreach (self.__copy_to_new_metadata_foreach, (metadata, unsaved_revision))

        shutil.rmtree (self.revisions_path)
        os.mkdir (self.revisions_path)

        self.metadata.freeDoc ()
        self.metadata = metadata
        self.unsaved_revision = unsaved_revision
        self.needs_saving = True

    def revert (self, revision, path = None):
        """Revert @profile, or a specific @path in @profile to
        a given @revision.

        @revision: the profile, file or directory revision to revert
        @profile (or @path, if given) to. A file or directory revision
        may only be used if @path is given.
        @path: the (optional) path of the file or directory which
        should be reverted.
        """
        if path:
            dprint ("Reverting '%s' to revision '%s'", path, revision)
        else:
            dprint ("Reverting profile '%s' to revision '%s'", self.name, revision)
        
        self.__unpack ()
        
        extract_dir = tempfile.mkdtemp (prefix = "sabayon-profile-storage-")
        
        (revision_type, revision_number) = revision.split (":")
        if revision_type == "profile":
            # Create new revision and remove everything
            def remove_from_current_foreach (source, path, self):
                self.remove (path)
            self.foreach (remove_from_current_foreach, self)

            # Add everything from @revision
            def add_from_revision_foreach (source, path, data):
                (self, extract_dir) = data
                self.extract (path, extract_dir, revision = revision)
                attributes = self.get_attributes (path, revision)
                self.add (path, extract_dir, source, attributes)
            self.foreach (add_from_revision_foreach,
                          (self, extract_dir),
                          profile_revision = revision)
        else:
            assert path
            self.extract (path, extract_dir, revision = revision)
            attributes = self.get_attributes (path, revision)
            source = self.get_source (path, revision)
            self.add (path, extract_dir, source, attributes)
            
        shutil.rmtree (extract_dir)

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

    # Now, re-open and validate
    profile = ProfileStorage (profile_path)

    # We should have three revisions, we saved thrice
    profile_revisions = profile.get_revisions ()
    assert len (profile_revisions) == 3
    assert profile_revisions[0][0] == "profile:3"
    assert profile_revisions[1][0] == "profile:2"
    assert profile_revisions[2][0] == "profile:1"

    # Verify the latest revision
    l = profile.list ()
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource99"
    assert path == "t/config1.test"
    assert profile.get_source (path) == "TestSource99"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr99")
    assert attributes["foo-attr99"] == "foo"
    assert attributes.has_key ("bar-attr99")
    assert attributes["bar-attr99"] == "99"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 2
    assert revisions[0][0] == "file:2"
    assert revisions[1][0] == "file:1"

    (source, path) = l[1]
    assert source == "TestSource2005"
    assert path == "foobar"
    assert profile.get_source (path) == "TestSource2005"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2005")
    assert attributes["foo-attr2005"] == "foo"
    assert attributes.has_key ("bar-attr2005")
    assert attributes["bar-attr2005"] == "2005"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 2
    assert revisions[0][0] == "directory:2"
    assert revisions[1][0] == "directory:1"

    (source, path) = l[2]
    assert source == "TestSource2"
    assert path == "config2.test"
    assert profile.get_source (path) == "TestSource2"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 0
    revisions = profile.get_revisions (path)
    assert len (revisions) == 2
    assert revisions[0][0] == "file:2"
    assert revisions[1][0] == "file:1"
    
    # Create temporary dir for extraction
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        profile.extract (path, temp_dir)

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


    # Verify the second revision
    l = profile.list (profile_revision = profile_revisions[1][0])
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource99"
    assert path == "t/config1.test"
    assert profile.get_source (path) == "TestSource99"
    attributes = profile.get_attributes (path, profile_revisions[1][0])
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr99")
    assert attributes["foo-attr99"] == "foo"
    assert attributes.has_key ("bar-attr99")
    assert attributes["bar-attr99"] == "99"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 2
    assert revisions[0][0] == "file:2"
    assert revisions[1][0] == "file:1"

    # Try using one of the file revisions
    assert profile.get_source (path, revisions[1][0]) == "TestSource1"
    attributes = profile.get_attributes (path, revisions[1][0])
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr1")
    assert attributes["foo-attr1"] == "foo"
    assert attributes.has_key ("bar-attr1")
    assert attributes["bar-attr1"] == "1"
    
    (source, path) = l[1]
    assert source == "TestSource2005"
    assert path == "foobar"
    assert profile.get_source (path, profile_revisions[1][0]) == "TestSource2005"
    attributes = profile.get_attributes (path, profile_revisions[1][0])
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2005")
    assert attributes["foo-attr2005"] == "foo"
    assert attributes.has_key ("bar-attr2005")
    assert attributes["bar-attr2005"] == "2005"
    
    (source, path) = l[2]
    assert source == "Waterford"
    assert path == "blaas"
    assert profile.get_source (path, profile_revisions[1][0]) == "Waterford"
    attributes = profile.get_attributes (path, profile_revisions[1][0])
    assert len (attributes) == 2
    assert attributes.has_key ("with-butter")
    assert attributes["with-butter"] == "but of course"
    assert attributes.has_key ("nice")
    assert attributes["nice"] == "True"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 1
    assert revisions[0][0] == "directory:1"

    # Create temporary dir for extraction
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        profile.extract (path, temp_dir, revision = profile_revisions[1][0])

    # Verify their contents
    assert os.path.isfile (os.path.join (temp_dir, "t/config1.test"))
    assert file (os.path.join (temp_dir, "t/config1.test")).read () == "new test file 99"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar/foo.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar/foo.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo.txt")).read () == "new test file 2005"
    assert os.path.isfile (os.path.join (temp_dir, "blaas/are/nice/foo.txt"))
    assert file (os.path.join (temp_dir, "blaas/are/nice/foo.txt")).read () == "blaas are nice"
    
    # Remove temporary extraction dir
    shutil.rmtree (temp_dir)

    
    # Verify the first revision
    l = profile.list (profile_revision = profile_revisions[2][0])
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource1"
    assert path == "t/config1.test"
    assert profile.get_source (path, profile_revisions[2][0]) == "TestSource1"
    attributes = profile.get_attributes (path, profile_revisions[2][0])
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr1")
    assert attributes["foo-attr1"] == "foo"
    assert attributes.has_key ("bar-attr1")
    assert attributes["bar-attr1"] == "1"
    
    (source, path) = l[1]
    assert source == "TestSource2"
    assert path == "config2.test"
    assert profile.get_source (path, profile_revisions[2][0]) == "TestSource2"
    attributes = profile.get_attributes (path, profile_revisions[2][0])
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2")
    assert attributes["foo-attr2"] == "foo"
    assert attributes.has_key ("bar-attr2")
    assert attributes["bar-attr2"] == "2"
    
    (source, path) = l[2]
    assert source == "TestSource3"
    assert path == "foobar"
    assert profile.get_source (path, profile_revisions[2][0]) == "TestSource3"
    attributes = profile.get_attributes (path, profile_revisions[2][0])
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr3")
    assert attributes["foo-attr3"] == "foo"
    assert attributes.has_key ("bar-attr3")
    assert attributes["bar-attr3"] == "3"

    # Create temporary dir for extraction
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        profile.extract (path, temp_dir, revision = profile_revisions[2][0])

    # Verify their contents
    assert os.path.isfile (os.path.join (temp_dir, "t/config1.test"))
    assert file (os.path.join (temp_dir, "t/config1.test")).read () == "new test file 1"
    assert os.path.isfile (os.path.join (temp_dir, "config2.test"))
    assert file (os.path.join (temp_dir, "config2.test")).read () == "new test file 2"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar/foo/bar/%gconf.xml")).read () == "new test file 3"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar/foo.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar/foo.txt")).read () == "new test file 4"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo/bar.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo/bar.txt")).read () == "new test file 5"
    assert os.path.isfile (os.path.join (temp_dir, "foobar/foo.txt"))
    assert file (os.path.join (temp_dir, "foobar/foo.txt")).read () == "new test file 6"
    
    # Remove temporary extraction dir
    shutil.rmtree (temp_dir)

    # Test reverting
    profile = ProfileStorage (profile_path)
    profile_revisions = profile.get_revisions ()
    assert len (profile_revisions) == 3
    assert profile_revisions[0][0] == "profile:3"
    assert profile_revisions[1][0] == "profile:2"
    assert profile_revisions[2][0] == "profile:1"

    # Revert whole thing to second revision
    profile.revert (profile_revisions[1][0])

    # Save
    os.remove (profile_path)
    profile.save ()
    assert os.path.exists (profile_path)

    # Open the reverted profile
    profile = ProfileStorage (profile_path)
    profile_revisions = profile.get_revisions ()
    assert len (profile_revisions) == 4
    assert profile_revisions[0][0] == "profile:4"
    assert profile_revisions[1][0] == "profile:3"
    assert profile_revisions[2][0] == "profile:2"
    assert profile_revisions[3][0] == "profile:1"

    # Verify the latest revision
    l = profile.list ()
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource99"
    assert path == "t/config1.test"
    assert profile.get_source (path) == "TestSource99"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr99")
    assert attributes["foo-attr99"] == "foo"
    assert attributes.has_key ("bar-attr99")
    assert attributes["bar-attr99"] == "99"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 3
    assert revisions[0][0] == "file:3"
    assert revisions[1][0] == "file:2"
    assert revisions[2][0] == "file:1"

    (source, path) = l[1]
    assert source == "TestSource2005"
    assert path == "foobar"
    assert profile.get_source (path) == "TestSource2005"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2005")
    assert attributes["foo-attr2005"] == "foo"
    assert attributes.has_key ("bar-attr2005")
    assert attributes["bar-attr2005"] == "2005"
    
    (source, path) = l[2]
    assert source == "Waterford"
    assert path == "blaas"
    assert profile.get_source (path) == "Waterford"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("with-butter")
    assert attributes["with-butter"] == "but of course"
    assert attributes.has_key ("nice")
    assert attributes["nice"] == "True"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 2
    assert revisions[0][0] == "directory:2"
    assert revisions[1][0] == "directory:1"

    # Clear revision history
    profile.clear_revisions ()

    # Save
    os.remove (profile_path)
    profile.save ()
    assert os.path.exists (profile_path)

    # We should only have a single revision now
    profile_revisions = profile.get_revisions ()
    assert len (profile_revisions) == 1
    assert profile_revisions[0][0] == "profile:1"

    # Verify this revision
    l = profile.list ()
    assert len (l) == 3

    (source, path) = l[0]
    assert source == "TestSource99"
    assert path == "t/config1.test"
    assert profile.get_source (path) == "TestSource99"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr99")
    assert attributes["foo-attr99"] == "foo"
    assert attributes.has_key ("bar-attr99")
    assert attributes["bar-attr99"] == "99"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 1
    assert revisions[0][0] == "file:1"

    (source, path) = l[1]
    assert source == "TestSource2005"
    assert path == "foobar"
    assert profile.get_source (path) == "TestSource2005"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("foo-attr2005")
    assert attributes["foo-attr2005"] == "foo"
    assert attributes.has_key ("bar-attr2005")
    assert attributes["bar-attr2005"] == "2005"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 1
    assert revisions[0][0] == "directory:1"

    (source, path) = l[2]
    assert source == "Waterford"
    assert path == "blaas"
    assert profile.get_source (path) == "Waterford"
    attributes = profile.get_attributes (path)
    assert len (attributes) == 2
    assert attributes.has_key ("with-butter")
    assert attributes["with-butter"] == "but of course"
    assert attributes.has_key ("nice")
    assert attributes["nice"] == "True"
    revisions = profile.get_revisions (path)
    assert len (revisions) == 1
    assert revisions[0][0] == "directory:1"
    
    # Create temporary dir for extraction
    temp_dir = tempfile.mkdtemp (prefix = "storage-test-")

    # Extract each of the files/directories
    for (source, path) in l:
        profile.extract (path, temp_dir)

    # Verify their contents
    assert os.path.isfile (os.path.join (temp_dir, "t/config1.test"))
    assert file (os.path.join (temp_dir, "t/config1.test")).read () == "new test file 99"
    assert os.path.isfile (os.path.join (temp_dir, "blaas/are/nice/foo.txt"))
    assert file (os.path.join (temp_dir, "blaas/are/nice/foo.txt")).read () == "blaas are nice"
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
