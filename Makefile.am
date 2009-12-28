SUBDIRS =			\
	lib			\
	admin-tool		\
	data			\
	help			\
	man			\
	po

EXTRA_DIST =			\
	pycheckrc		\
	sabayon.schema		\
	gnome-doc-utils.make \
	ISSUES

DISTCHECK_CONFIGURE_FLAGS = \
	--disable-scrollkeeper

pycheck:
	(cd lib; make pycheck) 
	(cd admin-tool; make pycheck) 
