PAGES=			\
	index.html	\
	developing.html	\
	testing.html	\
	helping.html

WSOURCES=		\
	flat.html	\
	site.xsl

EXTRA_DIST =		\
	$(PAGES)	\
	$(WSOURCES)

all:

rebuild: $(PAGES)

$(PAGES): $(WSOURCES)
	-@(if [ -x /usr/bin/xsltproc ] ; then 				\
	   /usr/bin/xsltproc -o index.html site.xsl flat.html ; fi)
