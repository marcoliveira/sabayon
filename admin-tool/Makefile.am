PYTHON_FILES =				\
	sabayon.py			\
	monitorwindow.py

GLADE_FILES =				\
	sabayon.glade

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(GLADE_FILES)			\
	sabayon.in			\
	profilesdialog.in		\
	profilesdialog			\
	sabayon

gladedir   = $(pkgdatadir)/glade
glade_DATA = $(GLADE_FILES)

install-exec-local:
	mkdir -p $(DESTDIR)$(sbindir)/
	install -m 0755 $(srcdir)/sabayon $(DESTDIR)$(bindir)
	mkdir -p $(DESTDIR)$(pkgdatadir)/
	for f in $(PYTHON_FILES); do \
	  install -m 0644 $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/ ; \
	done

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/*py
	rmdir $(DESTDIR)$(pkgdatadir)/
	rm -f $(DESTDIR)$(sbindir)/sabayon
	rmdir $(DESTDIR)$(sbindir)/

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)

BUILT_SOURCES = sabayon profilesdialog

all-local: sabayon profilesdialog

sabayon: sabayon.in
	sed -e s!\@PKGDATADIR\@!$(pkgdatadir)! < $< > $@
	chmod a+x $@

profilesdialog: profilesdialog.in
	sed -e s!\@PKGDATADIR\@!$(pkgdatadir)! < $< > $@
	chmod a+x $@
