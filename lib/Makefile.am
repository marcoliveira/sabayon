NULL = 

SUBDIRS = sources

INCLUDES = 				\
	$(WARN_CFLAGS)			\
	$(NO_STRICT_ALIASING_CFLAGS)	\
	$(PYTHON_INCLUDES)		\
	$(XLIB_MODULE_CFLAGS)		\
	$(X_CFLAGS)			\
	$(NULL)

sabayon_LTLIBRARIES = xlib.la

xlib_la_LDFLAGS = -module -avoid-version -fPIC -export-symbols-regex initxlib
xlib_la_LIBADD  = $(XLIB_MODULE_LIBS) $(X_LIBS)
xlib_la_SOURCES = xlib.c

PYTHON_FILES =				\
	__init__.py			\
	cache.py			\
	config.py			\
	errors.py			\
	debuglog.py			\
	dirmonitor.py			\
	mozilla_bookmarks.py		\
	protosession.py			\
	storage.py			\
	userdb.py			\
	usermod.py			\
	userprofile.py			\
	util.py

NOINST_PYTHON_FILES =			\
	test-debug-log.py		\
	unittests.py

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(NOINST_PYTHON_FILES)		\
	config.py.in

sabayondir     = $(pyexecdir)/sabayon
sabayon_PYTHON = $(PYTHON_FILES)

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES) $(NOINST_PYTHON_FILES)
	(cd sources; make pycheck)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)

DISTCLEANFILES = config.py
BUILT_SOURCES = config.py

config.py: config.py.in Makefile
	sed							\
                -e s!\@BINDIR\@!$(bindir)!			\
                -e s!\@SBINDIR\@!$(sbindir)!			\
                -e s!\@LIBEXECDIR\@!$(libexecdir)!		\
                -e s!\@LOCALEDIR\@!$(datadir)/locale!		\
                -e s!\@DATADIR\@!$(datadir)!			\
                -e s!\@SYSCONFDIR\@!$(sysconfdir)!		\
                -e s!\@PACKAGE_NAME\@!$(PACKAGE_NAME)!		\
                -e s!\@PACKAGE_VERSION\@!$(PACKAGE_VERSION)!	\
		-e s!\@XSESSION\@!$(XSESSION)!			\
		-e s!\@XNEST_PATH\@!$(XNEST_PATH)!		\
		-e s!\@SESSION_NAME\@!$(SESSION_NAME)!		\
		-e s!\@PROTOTYPE_USER\@!$(PROTOTYPE_USER)!	\
                < $< > $@
