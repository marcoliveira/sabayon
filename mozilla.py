#!/usr/bin/env python

import exceptions, sys, os.path, ConfigParser, re, cPickle

# ------ Globals ------


# ------ Excpetions ------

class FileNotFoundError(Exception):
    def __init__(self, filename):
        self.filename = filename
    def __str__(self):
        return "File Not Found (%s)" % self.filename
    
class BadIniFileError(Exception):
    def __init__(self, problem):
        self.problem = problem
    def __str__(self):
        return self.problem
    

# ------ Class DictCompare ------

class DictCompare:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def compare(self):
        ''' Given two dictionaries a,b analyze them for their
        differences and similarities.

        intersection - keys shared between a and b
        only_a       - keys only present in a
        only_b       - keys only present in b
        equal        - keys present in both a and b whole values are equal
        not_equal    - keys present in both a and b whole values are not equal'''

        self.keys_a = self.a.keys()
        self.keys_b = self.b.keys()
        
        self.intersection = []
        self.only_a = []
        self.only_b = []
        self.equal = []
        self.not_equal = []

        for k in self.keys_a:
            if self.b.has_key(k):
                self.intersection.append(k)
            else:
                self.only_a.append(k)

        for k in self.keys_b:
            if not self.a.has_key(k):
                self.only_b.append(k)
                
        for k in self.intersection:
            if self.a[k] == self.b[k]:
                self.equal.append(k)
            else:
                self.not_equal.append(k)
                
    def intersection(self):
        'return list of keys shared between a and b'
        return self.intersection

    def only_a(self):
        'return list of keys only present in a'
        return self.only_a

    def only_b(self):
        'return list of keys only present in b'
        return self.only_b

    def equal(self):
        'return list of keys present in both a and b whole values are equal'
        return self.equal

    def not_equal(self):
        'return list of keys present in both a and b whole values are not equal'
        return self.not_equal

    def get_change_set(self, dict_lhs, dict_rhs):
        '''Return changes necessary to make dict_lhs equivalent to dict_rhs,
        (e.g. lhs = rhs), the two dictionary parameters are specified as
        either the string 'a' or the string 'b' corresponding parameters this
        class was created with.
        
        Return value is a dictionary with 3 keys (add, del, mod) whose values
        are dictionaries containing containing (key,value) pairs to add,
        delete, or modify respectively in dict_lhs.'''

        if dict_lhs == dict_rhs or dict_lhs not in "ab" or dict_rhs not in "ab":
            raise ValueError

        if dict_lhs == 'a':
            a = self.a
            b = self.b
            only_a = self.only_a
            only_b = self.only_b
        elif dict_lhs == 'b':
            a = self.b
            b = self.a
            only_a = self.only_b
            only_b = self.only_a
        else:
            raise ValueError

        _add = {}
        for k in only_b:
            _add[k] = b[k]

        _del = {}
        for k in only_a:
            _del[k] = a[k]

        _mod = {}
        for k in self.not_equal:
            _mod[k] = b[k]

        change_set = {'add':_add, 'del':_del, 'mod':_mod}
        return change_set


    def dump(self):
        'Print the results of the dictionary comparision'
        print "intersection = %s" % ",".join(self.intersection)
        print "only a = %s" % ",".join(self.only_a)
        print "only b = %s" % ",".join(self.only_b)
        print "equal = %s" % ",".join(self.equal)
        print "not equal = %s" % ",".join(self.not_equal)


# ------ Class JavascriptPrefsFile ------

class JavascriptPrefsFile:
    def __init__(self, filepath):
        self.filepath = filepath

    def open(self):
        '''Constructors shouldn't do heavy processing or anything that might
        raise exceptions, its bad practice, so put the real work here in open.'''
        fd = open(self.filepath)
        self.filebuf = fd.read()
        fd.close()
        #print self.filebuf

    def kill_comments(self):
        slash_comment_re = re.compile("//.*$", re.MULTILINE)
        hash_comment_re = re.compile("#.*$", re.MULTILINE)
        c_comment_re = re.compile("/\*.*?\*/", re.MULTILINE | re.DOTALL)

        self.filebuf = slash_comment_re.sub("", self.filebuf)
        self.filebuf = hash_comment_re.sub("", self.filebuf)
        self.filebuf = c_comment_re.sub("", self.filebuf)

    def parse(self):
        # XXX - Warning: this regular expression is not perfectly robust
        # the 1st parameter is expected to be a double quoted string without
        # commas in it nor escaped double quotes. The parsing of the 2nd parameter
        # should be robust. For our expected input it should be fine. Really
        # robust parsing would require tokeninzing the expression.
        pref_re = re.compile("user_pref\s*\(\s*\"([^,\"]+)\s*\"\s*,\s*(.+?)\)\s*;\s*$", re.MULTILINE)
        start = 0;
        self.prefs = {}

        while 1:
            match = pref_re.search(self.filebuf, start)
            if match:
                key   = match.group(1)
                value = match.group(2)
                #print "(%d:%d) key='%s' value='%s'" % (match.start(), match.end(), key, value)
                self.prefs[key] = value
                start = match.end()
            else:
                break

    def dump_prefs(self):
        keys = self.prefs.keys()
        keys.sort()
        for key in keys:
            print "%s=%s" % (key, self.prefs[key])


# ------ Class UserProfile ------

class UserProfile:
    def __init__(self, ini_file_path):
        self.ini_file_path = ini_file_path

    def open(self):
        '''Constructors shouldn't do heavy processing or anything that might
        raise exceptions, its bad practice, so put the real work here in open.'''
        self.ini = ConfigParser.ConfigParser()
        self.ini.read(self.ini_file_path)
        self.profiles = {}
        self.default = None

    def get_profiles(self):
        profile_re = re.compile("^Profile(\d+)$")
        for section in self.ini.sections():
            match = profile_re.match(section)
            if match:
                name = self.ini.get(section, "Name")
                path = self.ini.get(section, "Path")
                try:
                    default = self.ini.get(section, "Default")
                except ConfigParser.NoOptionError:
                    default = None
                
                if name in self.profiles:
                    raise BadIniFileError("duplicate name (%s) in section %s" % (name, section))
                profile = {}
                self.profiles[name] = profile
                profile["section"] = section
                profile["path"] = path
                if default:
                    if self.default:
                        raise BadIniFileError("redundant default in section %s" % section)
                    self.default = name
                
    def get_default_path(self):
        if not self.default:
            raise BadIniFileError("no default profile")
        path = self.profiles[self.default]["path"]
        fullpath = "%s/%s" % (os.path.dirname(self.ini_file_path), path)
        if not os.path.exists(fullpath):
            raise BadIniFileError("default path (%s) does not exist" % fullpath)
        if not os.path.isdir(fullpath):
            raise BadIniFileError("default path (%s) is not a directory" % fullpath)
        return fullpath


# ------ Utility Functions ------

# XXX - this needs more logic to distinquish mozilla, firefox, versions, etc.
# basically its just hardcoded at the moment.
def GetProfileIniFile():
    filename = os.path.expanduser("~/.mozilla/firefox/profiles.ini")

    # XXX - should caller thow error instead?
    if not os.path.exists(filename):
        raise FileNotFoundError(filename)

    return(filename)

def write_dict(dict, path):
    fd = open(path, 'w')
    cPickle.dump(dict, fd, True)
    fd.close()

def read_dict(path):
    fd = open(path)
    dict = cPickle.load(fd)
    fd.close()
    return dict

def dump_change_set(cs):
    _add = cs['add']
    _del = cs['del']
    _mod = cs['mod']

    if len(_add.keys()):
        print "Key/Values to ADD"
        for k in _add.keys():
            print "    %s=%s" % (k, _add[k])

    if len(_del.keys()):
        print "Keys to DELETE"
        for k in _del.keys():
            print "    %s=%s" % (k, _del[k])

    if len(_mod.keys()):
        print "Key/Values to Modify"
        for k in _mod.keys():
            print "    %s=%s" % (k, _mod[k])


# ------ main ------
try:
    profile_ini_file = GetProfileIniFile()
except FileNotFoundError, e:
    print "No such profile ini file: %s" % e.filename
    sys.exit(1)

print "ini file = %s" % profile_ini_file

up = UserProfile(profile_ini_file)
up.open()
up.get_profiles()
default_path = up.get_default_path()
print "default_path = %s" % default_path

prefs_path = "%s/%s" % (default_path, "prefs.js")
prefs_save_path = "%s/%s" % (default_path, "prefs-save")
pref = JavascriptPrefsFile(prefs_path)
pref.open()
pref.kill_comments()
pref.parse()
#pref.dump_prefs()
write_dict(pref.prefs, prefs_save_path)

print >>sys.stdout, "Now modify %s" % prefs_path
print >>sys.stdout, "Hit return when done"
sys.stdin.readline()

prev_prefs = read_dict(prefs_save_path)

pref = JavascriptPrefsFile(prefs_path)
pref.open()
pref.kill_comments()
pref.parse()
#pref.dump_prefs()

dc = DictCompare(prev_prefs, pref.prefs)
dc.compare()
#dc.dump()

print "a <-- b"
cs = dc.get_change_set('a', 'b')
dump_change_set(cs)

print
print "b <-- a"
cs = dc.get_change_set('b', 'a')
dump_change_set(cs)
