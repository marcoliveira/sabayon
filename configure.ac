AC_INIT([sabayon], [0.10],
        [http://bugzilla.gnome.org/enter_bug.cgi?product=sabayon])
AC_CONFIG_SRCDIR(lib/userprofile.py)


AM_INIT_AUTOMAKE
AM_MAINTAINER_MODE

dnl make sure we keep ACLOCAL_FLAGS around for maintainer builds to work
AC_SUBST(ACLOCAL_AMFLAGS, "\${ACLOCAL_FLAGS}")

 
GETTEXT_PACKAGE=sabayon
AC_SUBST(GETTEXT_PACKAGE)

ALL_LINGUAS="cs de en_CA en_GB pt_BR sv zh_CN"
AM_GLIB_GNU_GETTEXT


AC_ARG_ENABLE(console-helper,
  [  --enable-console-helper=[auto/no/yes]  Enable PAM console helper [default=auto]],,
  enable_console_helper=auto)


withval=""
AC_ARG_WITH(pam-prefix,
[      --with-pam-prefix=<prefix>   specify where pam files go],[
if test x$withval != x; then
   AC_MSG_RESULT("PAM files will be installed in prefix ${withval}.")
fi])
if test x$withval != x; then
        PAM_PREFIX_UNEXPANDED="$withval"
else
        PAM_PREFIX_UNEXPANDED="$sysconfdir"
fi
PAM_PREFIX=`eval echo $PAM_PREFIX_UNEXPANDED`
AC_SUBST(PAM_PREFIX)


AM_PATH_PYTHON
AC_PROG_INTLTOOL
AC_PROG_LN_S


AC_PATH_PROG(CONSOLE_HELPER,consolehelper,no)
if test "x$CONSOLE_HELPER" = "xno" ; then
  if test "x$enable_console_helper" = "xyes" ; then
    AC_MSG_ERROR(Console helper requested but consolehelper binary not found)
  fi
  # if it was no, nothing happens, if it was auto, well then we're out of luck
  enable_console_helper=no
else
  if test ! "x$enable_console_helper" = "xno" ; then
    enable_console_helper=yes
  fi
fi

if test "x$enable_console_helper" = "xyes"; then
  AM_CONDITIONAL(CONSOLE_HELPER, true)
else
  AM_CONDITIONAL(CONSOLE_HELPER, false)
fi


AC_CONFIG_FILES([
Makefile
lib/Makefile
lib/sources/Makefile
admin-tool/Makefile
po/Makefile.in
])

AC_OUTPUT
