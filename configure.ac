AC_INIT([sabayon], [0.17],
        [http://bugzilla.gnome.org/enter_bug.cgi?product=sabayon])
AC_CONFIG_SRCDIR(lib/userprofile.py)


AM_INIT_AUTOMAKE
AM_MAINTAINER_MODE

dnl make sure we keep ACLOCAL_FLAGS around for maintainer builds to work
AC_SUBST(ACLOCAL_AMFLAGS, "\${ACLOCAL_FLAGS}")

 
GETTEXT_PACKAGE=sabayon
AC_SUBST(GETTEXT_PACKAGE)

ALL_LINGUAS="bg cs de el en_CA en_GB nb no pt_BR sv zh_CN"
AM_GLIB_GNU_GETTEXT


AC_ARG_WITH(distro,
            AC_HELP_STRING([--with-distro=DISTRO],
                           [Specify the Linux distribution to target: One of redhat or debian]))

if test "x$with_distro" = "x"; then
  AC_CHECK_FILE(/etc/redhat-release, with_distro="redhat")
  AC_CHECK_FILE(/etc/fedora-release, with_distro="redhat")
  AC_CHECK_FILE(/etc/debian_version, with_distro="debian")
  AC_CHECK_FILE(/etc/slackware-version, with_distro="slackware")
fi
with_distro=`echo ${with_distro} | tr '[[:upper:]]' '[[:lower:]]' `

if test "x$with_distro" = "x"; then
  echo "Linux distribution autodetection failed, you must specify the distribution to target using --with-distro=DISTRO"
  exit 1
else
  case $with_distro in
    redhat) 
      XSESSION="/etc/X11/xdm/Xsession"
      install_xinitrc_script="yes"
      XINITRC_SYSCONFDIR="X11/xinit/xinitrc.d"
      ;;
    debian) 
      XSESSION="/etc/gdm/Xsession"
      install_xinitrc_script="no"
      XINITRC_SYSCONFDIR=""
      ;;
    slackware)
      XSESSION="/etc/X11/gdm/Xsession"
      install_xinitrc_script="no"
      XINITRC_SYSCONFDIR=""
      ;;
    *)
      echo "Your distribution (${with_distro}) is not yet supported!  (patches welcome)"
      exit 1
      ;;
  esac
fi
AC_SUBST(XSESSION)
AC_SUBST(XINITRC_SYSCONFDIR)
AM_CONDITIONAL(INSTALL_XINITRC_SCRIPT, test "x$install_xinitrc_script" = "xyes")


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


# find the actual value for $prefix that we'll end up with
REAL_PREFIX=
if test "x$prefix" = "xNONE"; then
  REAL_PREFIX=$ac_default_prefix
else
  REAL_PREFIX=$prefix
fi
old_prefix=$prefix
prefix=$REAL_PREFIX

REAL_EXEC_PREFIX=
if test "x$exec_prefix" = "xNONE"; then
  REAL_EXEC_PREFIX=$prefix
else
  REAL_EXEC_PREFIX=$exec_prefix
fi
old_exec_prefix=$exec_prefix
exec_prefix=$REAL_EXEC_PREFIX


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
  SABAYON_DIR_TMP="$sbindir"
else
  AM_CONDITIONAL(CONSOLE_HELPER, false)
  SABAYON_DIR_TMP="$bindir"
fi

AC_CHECK_PROG(XNEST,Xnest,yes,no)
if test "x$XNEST" = "xno" ; then
  AC_MSG_WARN(xnest binary not found)
fi

EXPANDED_SABAYON_DIR=`eval echo $SABAYON_DIR_TMP`
AC_SUBST(EXPANDED_SABAYON_DIR)


AC_CONFIG_FILES([
Makefile
lib/Makefile
lib/sources/Makefile
doc/Makefile
admin-tool/Makefile
admin-tool/sabayon.console
po/Makefile.in
])

AC_OUTPUT
