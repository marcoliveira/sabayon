<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
  <xsl:output method="xml" encoding="ISO-8859-1" indent="yes"
      doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN"
      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>

<!--
 - returns the filename associated to an ID in the original file
 -->
  <xsl:template name="filename">
    <xsl:param name="name" select="string(@href)"/>
    <xsl:choose>
      <xsl:when test="$name = '#index'">
        <xsl:text>index.html</xsl:text>
      </xsl:when>
      <xsl:when test="$name = '#testing'">
        <xsl:text>testing.html</xsl:text>
      </xsl:when>
      <xsl:when test="$name = '#developing'">
        <xsl:text>developing.html</xsl:text>
      </xsl:when>
      <xsl:when test="$name = '#helping'">
        <xsl:text>helping.html</xsl:text>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$name"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
<!--
 - The global title
 -->
  <xsl:variable name="globaltitle" select="string(/html/body/h1[1])"/>
<!--
 - The download box
 -->
  <xsl:template name="download">
    <div class="box">
      <h2 class="box_title">Download</h2>
      <h4 class="box_header">RPMs</h4>
      <ul>
        <li>Mark provides <a href="http://people.redhat.com/markmc/sabayon/">RPMs for Rawhide</a></li>
      </ul>
      <h4 class="box_header">Source</h4>
      <ul>
        <li> <a href="http://ftp.gnome.org/pub/GNOME/sources/sabayon/">tarball</a></li>
	<li> <a href="http://cvs.gnome.org/viewcvs/sabayon/">CVS Repository</a></li>
      </ul>
    </div>
  </xsl:template>
<!--
  the contribute box
 -->
  <xsl:template name="contribute">
    <div class="box">
      <h2 class="box_title">Contribute</h2>
      <p>There are several ways to contribute to the Sabayon project.</p>
      <p><a href="testing.html">Testing</a>, go here if you want to install sabayon and try it out.</p>
      <p><a href="developing.html">Developing</a>, get the code and try to fix errors and send patches to the maintainers.</p>
      <p><a href="helping.html">Helping out</a> on the <a href="http://mail.gnome.org/mailman/listinfo/sabayon-list/">mailing list</a> and <a href="irc://irc.gnome.org/sabayon">IRC</a> for people having problems, letting them know where to go and what to do.</p>
    </div>
  </xsl:template>

<!--
  the contact box
 -->
  <xsl:template name="contact">
    <div class="box">
      <h2 class="box_title">Contact</h2>
      <p>You can contact developers <a href="mailto:sabayon-list@gnome.org">sending a mail</a> to the <a href="http://mail.gnome.org/mailman/listinfo/sabayon-list/">Sabayon mailing list</a>. You do not need to be subscribed.</p>
      <p>We are also often available to <a href="irc://irc.gnome.org/sabayon">chat on IRC</a>.</p>
      <p><strong>Server:</strong> irc.gnome.org<br /><strong>Channel:</strong> #sabayon</p>
    </div>
  </xsl:template>

<!--
 - Write the styles in the head
 -->
  <xsl:template name="style">
    <link rel="stylesheet" type="text/css" href="sabayon.css" />
  </xsl:template>

<!--
 - The top section
 -->
  <xsl:template name="top">
    <div id="top">
      <img src="title01.jpg" border="0" height="229" width="432" alt="Sabayon: user profiles made simple" /><img src="title02.jpg" border="0" height="229" alt="Small screenshot of sabayon" />
    </div>
  </xsl:template>

<!--
 - The bottom section
 -->
  <xsl:template name="bottom">
    <div id="copyright"> </div> 
  </xsl:template>

<!--
 - Handling of nodes in the body after an H2
 - Open a new file and dump all the siblings up to the next H2
 -->
  <xsl:template name="subfile">
    <xsl:param name="header" select="following-sibling::h2[1]"/>
    <xsl:variable name="filename">
      <xsl:call-template name="filename">
        <xsl:with-param name="name" select="concat('#', string($header/a[1]/@name))"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:variable name="title">
      <xsl:value-of select="$header"/>
    </xsl:variable>
    <xsl:document href="{$filename}" method="xml" encoding="ISO-8859-1"
      doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN"
      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
      <html>
        <head>
          <xsl:call-template name="style"/>
          <xsl:element name="title">
            <xsl:value-of select="$title"/>
          </xsl:element>
        </head>
        <body>
	  <div id="main">
	    <xsl:call-template name="top"/>
	    <div id="left">
	      <xsl:call-template name="download"/>
	      <xsl:call-template name="contribute"/>
	      <xsl:call-template name="contact"/>
	    </div>
	    <div id="right">
	      <xsl:apply-templates mode="subfile" select="$header/following-sibling::*[preceding-sibling::h2[1] = $header and name() != 'h2' ]"/>
	    </div>
	    <xsl:call-template name="bottom"/>
	  </div>
        </body>
      </html>
    </xsl:document>
  </xsl:template>

  <xsl:template mode="subcontent" match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates mode="subcontent" select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template mode="content" match="@*|node()">
    <xsl:if test="name() != 'h1' and name() != 'h2'">
      <xsl:copy>
        <xsl:apply-templates mode="subcontent" select="@*|node()"/>
      </xsl:copy>
    </xsl:if>
  </xsl:template>

  <xsl:template mode="subfile" match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates mode="content" select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

<!--
 - Handling of the initial body and head HTML document
 -->
  <xsl:template match="body">
    <xsl:variable name="firsth2" select="./h2[1]"/>
    <body>
      <div id="main">
	<xsl:call-template name="top"/>
        <div id="left">
	  <xsl:call-template name="download"/>
	  <xsl:call-template name="contribute"/>
	  <xsl:call-template name="contact"/>
        </div>
        <div id="right">
          <xsl:apply-templates mode="content" select="($firsth2/preceding-sibling::*)"/>
          <xsl:for-each select="./h2">
            <xsl:call-template name="subfile">
	      <xsl:with-param name="header" select="."/>
            </xsl:call-template>
          </xsl:for-each>
        </div>
        <xsl:call-template name="bottom"/>
      </div>
    </body>
  </xsl:template>
  <xsl:template match="head">
  </xsl:template>
  <xsl:template match="html">
    <xsl:message>Generating the Web pages</xsl:message>
    <html>
      <head>
        <xsl:call-template name="style"/>
        <title>User profiles made simple</title>
      </head>
      <xsl:apply-templates/>
    </html>
  </xsl:template>
</xsl:stylesheet>
