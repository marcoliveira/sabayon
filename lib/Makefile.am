SUBDIRS = sources

PYTHON_FILES =				\
	userprofile.py			\
	config.py			\
	storage.py			\
	dirmonitor.py			\
	protosession.py			\
	util.py

NOINST_PYTHON_FILES =			\
	unittests.py

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(NOINST_PYTHON_FILES)		\
	config.py.in

install-exec-local:
	mkdir -p $(DESTDIR)$(pkgdatadir)/
	for f in $(PYTHON_FILES); do \
	  install -m 0644 $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/ ; \
	done

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/*.py
	rmdir $(DESTDIR)$(pkgdatadir)/

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES) $(NOINST_PYTHON_FILES)
	(cd sources; make pycheck)

DISTCLEANFILES=config.py

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)

BUILT_SOURCES = config.py

all-local: config.py

config.py: config.py.in Makefile
	sed						\
                -e s!\@BINDIR\@!$(bindir)!		\
                -e s!\@SBINDIR\@!$(sbindir)!		\
                -e s!\@LIBEXECDIR\@!$(libexecdir)!	\
                -e s!\@PKGDATADIR\@!$(pkgdatadir)!	\
                -e s!\@SYSCONFDIR\@!$(sysconfdir)!	\
                < $< > $@
