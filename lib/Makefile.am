SUBDIRS = sources

PYTHON_FILES =				\
	userprofile.py			\
	config.py			\
	storage.py			\
	dirmonitor.py			\
	protosession.py			\
	usermod.py			\
	util.py

NOINST_PYTHON_FILES =			\
	unittests.py

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(NOINST_PYTHON_FILES)		\
	config.py.in

pkgdata_PYTHON = $(PYTHON_FILES)

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
                < $< > $@
