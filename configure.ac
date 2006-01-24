AC_INIT([sabayon], [2.12.3],
        [http://bugzilla.gnome.org/enter_bug.cgi?product=sabayon])
AC_CONFIG_SRCDIR(lib/userprofile.py)

AM_INIT_AUTOMAKE
AM_CONFIG_HEADER(config.h)
AM_MAINTAINER_MODE

# make sure we keep ACLOCAL_FLAGS around for maintainer builds to work
AC_SUBST(ACLOCAL_AMFLAGS, "\${ACLOCAL_FLAGS}")
 
GETTEXT_PACKAGE=sabayon
AC_SUBST(GETTEXT_PACKAGE)

ALL_LINGUAS="bg ca cs de el en_CA en_GB es fi fr gl gu hu ja lt nb ne no pa
pt_BR rw sr sr@Latn sv th uk vi zh_CN"
AM_GLIB_GNU_GETTEXT

AC_PROG_CC
AC_ISC_POSIX
AC_HEADER_STDC
AC_ARG_PROGRAM

AM_PROG_LIBTOOL
AM_PATH_PYTHON
AC_PROG_INTLTOOL
AC_PROG_LN_S

GNOME_COMPILE_WARNINGS(yes)

# Detect if we can build Python bindings (need python and python headers)
AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR([Can't locate python headers])])

# Check for GDK/X11 and PyGObject
PKG_CHECK_MODULES(XLIB_MODULE, gdk-x11-2.0 pygobject-2.0)
AC_SUBST(XLIB_MODULE_CFLAGS)
AC_SUBST(XLIB_MODULE_LIBS)

#
# If Pango included the shared library dependencies from X11 in
# the pkg-config output, then we use that (to avoid duplicates).
# but if they were omitted to avoid binary compatibility problems
# then we need to repeat the checks.
#
if $PKG_CONFIG --exists pangoxft ; then
  PANGO_PACKAGES="pangox pangoxft"
else
  PANGO_PACKAGES="pangox"
fi

x_libs="`$PKG_CONFIG --libs $PANGO_PACKAGES`"
case x_libs in
  *-lX11*) pango_omitted_x_deps=no ;;
  *)       pango_omitted_x_deps=yes ;;
esac

if test $pango_omitted_x_deps = yes ; then
  AC_PATH_XTRA

  if test x$no_x = xyes ; then
    AC_MSG_ERROR([X development libraries not found])
  else
    X_LIBS="$X_PRE_LIBS $X_LIBS -lX11 $X_EXTRA_LIBS"
  fi
fi

# Because of the way Python implements polymorphism, we get the following warning:
# "warning: dereferencing type-punned pointer will break strict-aliasing rules"
# -fno-strict-aliasing (as used in Python build) switches warnings off
NO_STRICT_ALIASING_CFLAGS=""
if test "x$GCC" = "xyes" ; then
  AC_MSG_CHECKING(whether $CC accepts -fno-strict-aliasing)
  ac_save_cc="$CC"
  CC="$CC -fno-strict-aliasing"
  AC_TRY_RUN([int main() { return 0; }],
             ac_cv_no_strict_aliasing_ok=yes,
             ac_cv_no_strict_aliasing_ok=no,
             ac_cv_no_strict_aliasing_ok=no)
  CC="$ac_save_cc"
  AC_MSG_RESULT($ac_cv_no_strict_aliasing_ok)
  if test "x$ac_cv_no_strict_aliasing_ok" = "xyes" ; then
    NO_STRICT_ALIASING_CFLAGS="-fno-strict-aliasing"
  fi
fi
AC_SUBST(NO_STRICT_ALIASING_CFLAGS)



AC_ARG_WITH(distro,
            AC_HELP_STRING([--with-distro=DISTRO],
                           [Specify the Linux distribution to target: One of redhat, debian, slackware, or gentoo]))

if test "x$with_distro" = "x"; then
  AC_CHECK_FILE(/etc/redhat-release, with_distro="redhat")
  AC_CHECK_FILE(/etc/fedora-release, with_distro="redhat")
  AC_CHECK_FILE(/etc/debian_version, with_distro="debian")
  AC_CHECK_FILE(/etc/slackware-version, with_distro="slackware")
  AC_CHECK_FILE(/etc/gentoo-release, with_distro="gentoo")
  AC_CHECK_FILE(/etc/SuSE-release, with_distro="suse")
  AC_CHECK_FILE(/etc/mandriva-release, with_distro="mandriva")
  AC_CHECK_FILE(/etc/mandrakelinux-release, with_distro="mandriva")
fi
with_distro=`echo ${with_distro} | tr '[[:upper:]]' '[[:lower:]]' `

if test "x$with_distro" = "x"; then
  echo "Linux distribution autodetection failed, you must specify the distribution to target using --with-distro=DISTRO"
  exit 1
else
  case $with_distro in
    redhat) 
      XSESSION="/etc/X11/xdm/Xsession"
      SESSION_NAME="gnome"
      install_xinitrc_script="yes"
      XINITRC_SYSCONFDIR="X11/xinit/xinitrc.d"
      ;;
    debian) 
      XSESSION="/etc/gdm/Xsession"
      SESSION_NAME="gnome-session"
      install_xinitrc_script="no"
      XINITRC_SYSCONFDIR=""
      ;;
    slackware)
      XSESSION="/etc/X11/gdm/Xsession"
      SESSION_NAME="gnome"
      install_xinitrc_script="no"
      XINITRC_SYSCONFDIR=""
      ;;
    gentoo)
      XSESSION="/etc/X11/xdm/Xsession"
      SESSION_NAME="gnome"
      install_xinitrc_script="no"
      XINITRC_SYSCONFDIR=""
      ;;
    suse)
      XSESSION="/etc/opt/gnome/gdm/Xsession"
      install_xinitrc_script="no"
      XINITRC_SYSCONFDIR="/etc/X11/xinit/xinitrc.d"
      ;;
    mandriva)
      XSESSION="/etc/X11/xdm/Xsession"
      SESSION_NAME="GNOME"
      install_xinitrc_script="yes"
      XINITRC_SYSCONFDIR="X11/xinit.d"
      ;;
    *)
      echo "Your distribution (${with_distro}) is not yet supported!  (patches welcome)"
      exit 1
      ;;
  esac
fi
AC_SUBST(XSESSION)
AC_SUBST(SESSION_NAME)
AC_SUBST(XINITRC_SYSCONFDIR)
AM_CONDITIONAL(INSTALL_XINITRC_SCRIPT, test "x$install_xinitrc_script" = "xyes")


AC_ARG_WITH(prototype-user,
            AC_HELP_STRING([--with-prototype-user=USERNAME],
                           [The username of the prototype user (defaults to "sabayon")]))

if test "x$with_prototype_user" != "x"; then
  PROTOTYPE_USER="$with_prototype_user"
else
  PROTOTYPE_USER="sabayon"
fi
AC_SUBST(PROTOTYPE_USER)

AC_ARG_ENABLE(console-helper,
  [  --enable-console-helper=[auto/no/yes]  Enable PAM console helper [default=auto]],,
  enable_console_helper=auto)


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

AC_PATH_PROG(XNEST_PATH,Xnest,no)
if test "x$XNEST_PATH" = "xno" ; then
  AC_MSG_ERROR(Xnest binary not found)
fi
AC_SUBST(XNEST_PATH)


EXPANDED_SABAYON_DIR=`eval echo $SABAYON_DIR_TMP`
AC_SUBST(EXPANDED_SABAYON_DIR)


AC_CONFIG_FILES([
Makefile
lib/Makefile
lib/sources/Makefile
doc/Makefile
admin-tool/Makefile
admin-tool/sabayon.console
admin-tool/lockdown/Makefile
po/Makefile.in
])

AC_OUTPUT
