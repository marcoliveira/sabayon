AC_INIT([sabayon], [0.10],
        [http://bugzilla.gnome.org/enter_bug.cgi?product=sabayon])
AC_CONFIG_SRCDIR(lib/userprofile.py)

AM_INIT_AUTOMAKE
AM_MAINTAINER_MODE

dnl make sure we keep ACLOCAL_FLAGS around for maintainer builds to work
AC_SUBST(ACLOCAL_AMFLAGS, "\${ACLOCAL_FLAGS}")
 
GETTEXT_PACKAGE=sabayon
AC_SUBST(GETTEXT_PACKAGE)

PYTHON=python
AC_SUBST(PYTHON)
 
ALL_LINGUAS="en_CA pt_BR sv zh_CN"
 
paths=`python <<EOF
import sys;
for p in sys.path:
   if len(p): print p
EOF`
 
AC_MSG_CHECKING([for your python path])
AC_SUBST(PY_PYTHONPATH)
PY_PYTHONPATH=`python2.3 <<EOF
import sys;
path=""
for p in sys.path:
   if len(p):
        if path: path=path + p + ":"
        else: path=p
print path;
EOF`
AC_MSG_RESULT([$PY_PYTHONPATH]);
 
AC_MSG_CHECKING([for compileall])
 
AC_SUBST(PY_COMPILEALL)
PY_COMPILEALL="/usr/lib/python2.3/compileall.pyc"
for p in $paths;do test -f "$p/compileall.pyc" && PY_COMPILEALL="$p/compileall.pyc" && break;done
 
if ! test -f $PY_COMPILEALL;then
        AC_MSG_ERROR([compileall.pyc not found in $PY_PYTHONPATH]);
else
        AC_MSG_RESULT([$PY_COMPILEALL]);
fi

AC_PROG_INTLTOOL
AC_PROG_LN_S

ALL_LINGUAS=""
AM_GLIB_GNU_GETTEXT

AC_CONFIG_FILES([
Makefile
lib/Makefile
lib/sources/Makefile
admin-tool/Makefile
po/Makefile.in
])

AC_OUTPUT
