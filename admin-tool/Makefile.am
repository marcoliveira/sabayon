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

desktopdir        = $(datadir)/applications
desktop_in_files = sabayon.desktop.in
desktop_DATA     = $(desktop_in_files:.desktop.in=.desktop)

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(GLADE_FILES)			\
	$(desktop_in_files)		\
	$(desktop_DATA)			\
	sabayon.in			\
	sabayon-monitor.in		\
	sabayon-session.in

gladedir   = $(pkgdatadir)/glade
glade_DATA = $(GLADE_FILES)

icondir    = $(datadir)/pixmaps
icon_DATA  = $(ICON_FILES)

wrappers = 			\
	sabayon			\
	sabayon-monitor		\
	sabayon-session

%: %.in
	sed -e s!\@PKGDATADIR\@!$(pkgdatadir)! < $< > $@
	sed -e s!\@SBINDIR\@!$(sbindir)! < $< > $@
	chmod a+x $@

sbin_SCRIPTS = sabayon
libexec_SCRIPTS = sabayon-monitor sabayon-session

pkgdata_PYTHON = $(PYTHON_FILES)

install-exec-local: sabayon.console
	mkdir -p $(DESTDIR)$(sysconfdir)/desktop-profiles/
if CONSOLE_HELPER
	$(INSTALL_DATA) -D $(srcdir)/sabayon.pam $(DESTDIR)$(PAM_PREFIX)/pam.d/sabayon
	$(INSTALL_DATA) -D sabayon.console $(DESTDIR)$(PAM_PREFIX)/security/console.apps/sabayon
	$(INSTALL_DATA) -m 755 -d $(DESTDIR)$(sbindir)
	mv -f $(DESTDIR)$(bindir)/sabayon $(DESTDIR)$(sbindir)
	$(LN_S) @CONSOLE_HELPER@ $(DESTDIR)$(bindir)/sabayon
endif

uninstall-local:
	rmdir $(DESTDIR)$(sysconfdir)/desktop-profiles/
if CONSOLE_HELPER
	rm -f $(DESTDIR)$(PAM_PREFIX)/pam.d/sabayon
	rm -f $(DESTDIR)$(PAM_PREFIX)/security/console.apps/sabayon
	rmdir $(DESTDIR)$(PAM_PREFIX)/pam.d
	rmdir $(DESTDIR)$(PAM_PREFIX)/security/console.apps
endif

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)

BUILT_SOURCES  = $(wrappers)
DISTCLEANFILES = $(wrappers)
