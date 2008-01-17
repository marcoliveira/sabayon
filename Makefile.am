SUBDIRS =			\
	lib			\
	admin-tool		\
	data			\
	doc			\
	po

EXTRA_DIST =			\
	pycheckrc		\
	intltool-extract.in	\
	intltool-merge.in	\
	intltool-update.in	\
	sabayon.schema		\
	ISSUES

DISTCLEANFILES =		\
	intltool-extract	\
	intltool-merge		\
	intltool-update

pycheck:
	(cd lib; make pycheck) 
	(cd admin-tool; make pycheck) 
