PAGES=			\
	index.html	\
	developing.html	\
	testing.html	\
	helping.html	\
	format.html	\
	config.html	\
	ldap.html

WSOURCES=		\
	flat.html	\
	site.xsl

IMGS=			\
	shadow.gif	\
	brownbar.jpg	\
	brownbarTop.jpg	\
	title01.jpg	\
	title02.jpg

EXTRA_DIST =		\
	$(PAGES)	\
	$(WSOURCES)	\
	$(IMGS)		\
	sabayon.css

all:

rebuild: $(PAGES)

$(PAGES): $(WSOURCES)
	-@(if [ -x /usr/bin/xsltproc ] ; then 				\
	   /usr/bin/xsltproc -o index.html site.xsl flat.html ; fi)
	-@(if [ -x /usr/bin/xmllint ] ; then				\
	   echo Validating the resulting pages ;			\
	   /usr/bin/xmllint --valid --noout $(PAGES)  ; fi)
