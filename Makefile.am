SUBDIRS =			\
	lib			\
	admin-tool		\
	doc			\
	po

EXTRA_DIST =			\
	pycheckrc		\
	intltool-extract.in	\
	intltool-merge.in	\
	intltool-update.in	\
	sabayon.spec.in		\
	sabayon.spec		\
	ISSUES

DISTCLEANFILES =		\
	intltool-extract	\
	intltool-merge		\
	intltool-update		\
	sabayon.spec

pycheck:
	(cd lib; make pycheck) 
	(cd admin-tool; make pycheck) 

sabayon.spec: sabayon.spec.in Makefile
	sed						\
                -e s!\@VERSION\@!$(PACKAGE_VERSION)!	\
                < $< > $@

rpm: sabayon.spec dist
	@(gzip -cd sabayon-$(PACKAGE_VERSION).tar.gz | bzip2 > sabayon-$(PACKAGE_VERSION).tar.bz2)
	@(rpmbuild -ta sabayon-$(PACKAGE_VERSION).tar.gz)
