SUBDIRS = storage-modules

PYTHON_FILES =				\
	userprofile.py			\
	config.py			\
	storage.py			\
	dirmonitor.py			\
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
	(cd storage-modules; make pycheck)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)

BUILT_SOURCES = config.py

all-local: config.py

config.py: config.py.in
	sed -e s!\@PKGDATADIR\@!$(pkgdatadir)! < $< > $@
