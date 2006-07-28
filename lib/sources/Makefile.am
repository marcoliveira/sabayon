PYTHON_FILES =				\
	gconfsource.py			\
	filessource.py			\
	mozillasource.py		\
	paneldelegate.py		\
	__init__.py

NOINST_PYTHON_FILES =			\
	testsource.py

EXTRA_DIST =				\
	$(PYTHON_FILES)			\
	$(NOINST_PYTHON_FILES)

sourcesdir     = $(pyexecdir)/sabayon/sources
sources_PYTHON = $(PYTHON_FILES)

pycheck:
	pychecker -F $(top_srcdir)/pycheckrc $(PYTHON_FILES) $(NOINST_PYTHON_FILES)

clean:
	rm -f *.pyo *.pyc
	rm -f $(BUILT_SOURCES)
