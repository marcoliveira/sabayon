PYTHON_FILES =				\
	gconfsource.py			\
	filessource.py			\
	mozillasource.py

NOINST_PYTHON_FILES =			\
	testmodule.py

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(NOINST_PYTHON_FILES)

install-exec-local:
	mkdir -p $(DESTDIR)$(pkgdatadir)/storage-modules/
	for f in $(PYTHON_FILES); do \
	  install -m 0644 $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/storage-modules/ ; \
	done

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/storage-modules/*.py
	rmdir $(DESTDIR)$(pkgdatadir)/storage-modules

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES) $(NOINST_PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)
