PYTHON_FILES =				\
	sabayon.py			\
	sabayon-monitor.py		\
	sabayon-session.py		\
	monitorwindow.py		\
	profilesdialog.py

@INTLTOOL_DESKTOP_RULE@

GLADE_FILES =				\
	sabayon.glade

ICON_FILES =				\
	sabayon.png

Applicationsdir = $(datadir)/applications
Applications_in_files = sabayon.desktop.in
Applications_DATA = $(Applications_in_files:.desktop.in=.desktop)

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(GLADE_FILES)			\
	$(Applications_in_files)	\
	$(Applications_DATA)		\
	sabayon.in			\
	sabayon-monitor.in		\
	sabayon-session.in

gladedir   = $(pkgdatadir)/glade
glade_DATA = $(GLADE_FILES)

icondir    = $(datadir)/pixmaps
icon_DATA  = $(ICON_FILES)

PAMD_DIR = /etc/pam.d
SECURITY_DIR = /etc/security/console.apps

install-exec-local:
	mkdir -p $(DESTDIR)$(sbindir)/
	install -m 0755 $(srcdir)/sabayon $(DESTDIR)$(sbindir)
	mkdir -p $(DESTDIR)$(libexecdir)/
	install -m 0755 $(srcdir)/sabayon-monitor $(DESTDIR)$(libexecdir)
	install -m 0755 $(srcdir)/sabayon-session $(DESTDIR)$(libexecdir)
	mkdir -p $(DESTDIR)$(pkgdatadir)/
	mkdir -p $(DESTDIR)$(sysconfdir)/desktop-profiles/
	for f in $(PYTHON_FILES); do \
	  install -m 0644 $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/ ; \
	done
	mkdir -p $(DESTDIR)$(PAMD_DIR)
	mkdir -p $(DESTDIR)$(SECURITY_DIR)
	install sabayon.pam $(DESTDIR)$(PAMD_DIR)/sabayon
	install sabayon.console $(DESTDIR)$(SECURITY_DIR)/sabayon
	ln -sf consolehelper $(DESTDIR)$(bindir)/sabayon

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/*py
	rmdir $(DESTDIR)$(pkgdatadir)/
	rm -f $(DESTDIR)$(sbindir)/sabayon
	rm -f $(DESTDIR)$(libexecdir)/sabayon-monitor
	rm -f $(DESTDIR)$(libexecdir)/sabayon-session
	rmdir $(DESTDIR)$(sbindir)/
	rmdir $(DESTDIR)$(libexecdir)/
	rmdir $(DESTDIR)$(sysconfdir)/desktop-profiles/
	rm -f $(DESTDIR)$(PAMD_DIR)/sabayon
	rm -f $(DESTDIR)$(SECURITY_DIR)/sabayon
	rmdir $(DESTDIR)$(PAMD_DIR)
	rmdir $(DESTDIR)$(SECURITY_DIR)

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

BUILT_SOURCES  = $(wrappers)
DISTCLEANFILES = $(wrappers)
