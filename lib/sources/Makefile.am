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
	mkdir -p $(DESTDIR)$(pkgdatadir)/sources/
	for f in $(PYTHON_FILES); do \
	  install -m 0644 $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/sources/ ; \
	done

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/sources/*.py
	rmdir $(DESTDIR)$(pkgdatadir)/sources

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES) $(NOINST_PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)
