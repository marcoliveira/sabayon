#!/bin/sh
# Run this to generate all the initial makefiles, etc.

PROJECT=sabayon

srcdir=`dirname $0`
test -z "$srcdir" && srcdir=.

THEDIR=`pwd`
cd $srcdir

DIE=0

(autoconf --version) < /dev/null > /dev/null 2>&1 || {
	echo
	echo "You must have autoconf installed to compile $PROJECT."
	echo "Download the appropriate package for your distribution,"
	echo "or get the source tarball at ftp://ftp.gnu.org/pub/gnu/"
	DIE=1
}

if automake-1.9 --version < /dev/null > /dev/null 2>&1; then
  AUTOMAKE=automake-1.9
  ACLOCAL=aclocal-1.9
elif automake-1.8 --version < /dev/null > /dev/null 2>&1; then
  AUTOMAKE=automake-1.8
  ACLOCAL=aclocal-1.8
elif automake-1.7 --version < /dev/null > /dev/null 2>&1; then
  AUTOMAKE=automake-1.7
  ACLOCAL=aclocal-1.7
else
        echo
        echo "You must have automake >= 1.7 installed to compile $PROJECT."
        echo "Get http://ftp.gnu.org/gnu/automake/automake-1.9.3.tar.bz2"
        echo "(or a newer version if it is available)"
        DIE=1
fi

if test "$DIE" -eq 1; then
	exit 1
fi

if test -z "$*"; then
	echo "I am going to run ./configure with no arguments - if you wish "
        echo "to pass any to it, please specify them on the $0 command line."
fi

glib-gettextize --copy --force
intltoolize --copy -f --automake

$ACLOCAL -I . $ACLOCAL_FLAGS
autoconf
$AUTOMAKE --add-missing $am_opt
cd $THEDIR

$srcdir/configure --enable-maintainer-mode "$@"

echo 
echo "Now type 'make' to compile $PROJECT."
