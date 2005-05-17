SUBDIRS = sources

PYTHON_FILES =				\
	__init__.py			\
	userprofile.py			\
	cache.py			\
	config.py			\
	storage.py			\
	dirmonitor.py			\
	mozilla_bookmarks.py		\
	protosession.py			\
	usermod.py			\
	userdb.py			\
	util.py

NOINST_PYTHON_FILES =			\
	unittests.py

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(NOINST_PYTHON_FILES)		\
	config.py.in

sabayondir     = $(pythondir)/sabayon
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
                -e s!\@DATADIR\@!$(datadir)!			\
                -e s!\@SYSCONFDIR\@!$(sysconfdir)!		\
                -e s!\@PACKAGE_NAME\@!$(PACKAGE_NAME)!		\
                -e s!\@PACKAGE_VERSION\@!$(PACKAGE_VERSION)!	\
		-e s!\@XSESSION\@!$(XSESSION)!			\
		-e s!\@PROTOTYPE_USER\@!$(PROTOTYPE_USER)!	\
                < $< > $@
