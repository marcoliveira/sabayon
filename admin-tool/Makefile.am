PYTHON_FILES =				\
	sabayon.py			\
	sabayon-monitor.py		\
	sabayon-session.py		\
	monitorwindow.py		\
	profilesdialog.py

GLADE_FILES =				\
	sabayon.glade

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(GLADE_FILES)			\
	sabayon.in			\
	sabayon-monitor.in		\
	sabayon-session.in

gladedir   = $(pkgdatadir)/glade
glade_DATA = $(GLADE_FILES)

install-exec-local:
	mkdir -p $(DESTDIR)$(sbindir)/
	install -m 0755 $(srcdir)/sabayon $(DESTDIR)$(sbindir)
	install -m 0755 $(srcdir)/sabayon-monitor $(DESTDIR)$(sbindir)
	install -m 0755 $(srcdir)/sabayon-session $(DESTDIR)$(sbindir)
	mkdir -p $(DESTDIR)$(pkgdatadir)/
	for f in $(PYTHON_FILES); do \
	  install -m 0644 $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/ ; \
	done

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/*py
	rmdir $(DESTDIR)$(pkgdatadir)/
	rm -f $(DESTDIR)$(sbindir)/sabayon
	rm -f $(DESTDIR)$(sbindir)/sabayon-monitor
	rm -f $(DESTDIR)$(sbindir)/sabayon-session
	rmdir $(DESTDIR)$(sbindir)/

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)

wrappers = 			\
	sabayon			\
	sabayon-monitor		\
	sabayon-session

all-local: $(wrappers)

%: %.in
	sed -e s!\@PKGDATADIR\@!$(pkgdatadir)! < $< > $@
	chmod a+x $@

BUILT_SOURCES = $(wrappers)
