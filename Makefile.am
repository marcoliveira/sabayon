SUBDIRS =			\
	lib			\
	admin-tool		\
	po

EXTRA_DIST =			\
	pycheckrc		\
	intltool-extract.in	\
	intltool-merge.in	\
	intltool-update.in

DISTCLEANFILES =		\
	intltool-extract	\
	intltool-merge		\
	intltool-update

pycheck:
	(cd lib; make pycheck) 
	(cd admin-tool; make pycheck) 
