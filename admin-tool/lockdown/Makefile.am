PESSULUSDIR=../../../pessulus
PESSULUSDATA=pessulus.ui
PESSULUSPYTHON= \
        disabledapplets.py      \
        icons.py                \
        globalvar.py            \
        lockdownapplier.py      \
        lockdownbutton.py       \
        lockdowncheckbutton.py  \
        lockdownappliergconf.py \
        maindialog.py           \
        safeprotocols.py        \
        simpleeditabletreeview.py

update:
	for file in $(PESSULUSDATA); do \
		cp $(PESSULUSDIR)/data/$$file . ;\
	done
	for file in $(PESSULUSPYTHON); do \
		cp $(PESSULUSDIR)/Pessulus/$$file . ;\
	done


PYTHON_FILES = $(PESSULUSPYTHON) __init__.py config.py
UI_FILES = pessulus.ui

uidir   = $(pkgdatadir)/ui
ui_DATA = $(UI_FILES)


EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(UI_FILES)

sabayonlockdowndir     = $(pyexecdir)/sabayon/lockdown
sabayonlockdown_PYTHON = $(PYTHON_FILES)

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
