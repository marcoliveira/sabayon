PESSULUSDIR=../../../pessulus
PESSULUSDATA=pessulus.glade
PESSULUSPYTHON= \
  disabledapplets.py        \
  icons.py                  \
  lockdownapplier.py        \
  lockdowncheckbutton.py    \
  maindialog.py             \
  safeprotocols.py          \
  simpleeditabletreeview.py

update:
	for file in $(PESSULUSDATA); do \
		cp $(PESSULUSDIR)/data/$$file . ;\
	done
	for file in $(PESSULUSPYTHON); do \
		cp $(PESSULUSDIR)/Pessulus/$$file . ;\
	done


PYTHON_FILES = $(PESSULUSPYTHON) __init__.py config.py
GLADE_FILES = pessulus.glade

gladedir   = $(pkgdatadir)/glade
glade_DATA = $(GLADE_FILES)


EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(GLADE_FILES)			

sabayonlockdowndir     = $(pythondir)/sabayon/lockdown
sabayonlockdown_PYTHON = $(PYTHON_FILES)

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
