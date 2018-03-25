<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:n="http://www.naptan.org.uk/"
               xmlns:func="http://nextbus.org/functions" 
               xmlns:exsl="http://exslt.org/common"
               xmlns:re="http://exslt.org/regular-expressions"
               exclude-result-prefixes="func exsl re">
  <xsl:output method="xml" indent="yes"/>
  <xsl:param name="stops" select="n:NaPTAN/n:StopPoints/n:StopPoint[boolean(n:NaptanCode)] 
    [@Status='active'][n:StopClassification/n:StopType[.='BCT' or .='BCS' or .='PLT']]
    [not(n:AdministrativeAreaRef[.='110' or .='143' or .='145' or .='146'])]"/>
  <xsl:param name="areas" select="n:NaPTAN/n:StopAreas/n:StopArea[@Status='active']
    [n:StopAreaType[.='GBPS' or .='GCLS' or .='GBCS' or .='GPBS' or .='GTMU']]
    [not(n:AdministrativeAreaRef[.='110' or .='143' or .='145' or .='146'])]"/>

  <xsl:template match="n:NaPTAN">
    <Data>
      <StopPoints>
        <xsl:apply-templates select="$stops"/>
      </StopPoints>
      <StopAreas>
        <xsl:apply-templates select="$areas"/>
      </StopAreas>
    </Data>
  </xsl:template>

  <xsl:template match="n:StopPoint">
    <StopPoint>
      <atco_code><xsl:value-of select="func:upper(n:AtcoCode)"/></atco_code>
      <naptan_code><xsl:value-of select="func:lower(n:NaptanCode)"/></naptan_code>
      <!-- Forward slash character is not allowed in NaPTAN data; was removed leaving 2 spaces -->
      <name><xsl:value-of select="func:replace(n:Descriptor/n:CommonName, '  ', ' / ')"/></name>
      <landmark>
        <xsl:call-template name="stop-descriptor">
          <xsl:with-param name="desc" select="n:Descriptor/n:Landmark"/>
        </xsl:call-template>
      </landmark>
      <street>
        <xsl:call-template name="stop-descriptor">
          <xsl:with-param name="desc" select="n:Descriptor/n:Street"/>
        </xsl:call-template>
      </street>
      <crossing>
        <xsl:call-template name="stop-descriptor">
          <xsl:with-param name="desc" select="n:Descriptor/n:Crossing"/>
        </xsl:call-template>
      </crossing>
      <indicator><xsl:value-of select="n:Descriptor/n:Indicator"/></indicator>
      <locality_ref><xsl:value-of select="n:Place/n:NptgLocalityRef"/></locality_ref>
      <easting><xsl:value-of select="n:Place/n:Location/n:Translation/n:Easting"/></easting>
      <northing><xsl:value-of select="n:Place/n:Location/n:Translation/n:Northing"/></northing>
      <longitude><xsl:value-of select="n:Place/n:Location/n:Translation/n:Longitude"/></longitude>
      <latitude><xsl:value-of select="n:Place/n:Location/n:Translation/n:Latitude"/></latitude>
      <stop_type><xsl:value-of select="n:StopClassification/n:StopType"/></stop_type>
      <bearing><xsl:value-of select=".//n:CompassPoint"/></bearing>
      <stop_area_ref><xsl:value-of select="n:StopAreas/n:StopAreaRef"/></stop_area_ref>
      <admin_area_ref><xsl:value-of select="n:AdministrativeAreaRef"/></admin_area_ref>
      <modified><xsl:value-of select="@ModificationDateTime"/></modified>
    </StopPoint>
  </xsl:template>

  <xsl:template match="n:StopArea">
    <StopArea>
      <code><xsl:value-of select="func:upper(n:StopAreaCode)"/></code>
      <name><xsl:value-of select="func:replace(n:Name, '  ', ' / ')"/></name>
      <admin_area_ref><xsl:value-of select="n:AdministrativeAreaRef"/></admin_area_ref>
      <stop_area_type>
        <xsl:choose>
          <!-- Stop type GPBS regularly mispelled as GBPS -->
          <xsl:when test="n:StopAreaType='GBPS'">GPBS</xsl:when>
          <xsl:otherwise><xsl:value-of select="n:StopAreaType"/></xsl:otherwise>
        </xsl:choose>
      </stop_area_type>
      <easting><xsl:value-of select="n:Location/n:Translation/n:Easting"/></easting>
      <northing><xsl:value-of select="n:Location/n:Translation/n:Northing"/></northing>
      <longitude><xsl:value-of select="n:Location/n:Translation/n:Longitude"/></longitude>
      <latitude><xsl:value-of select="n:Location/n:Translation/n:Latitude"/></latitude>
      <modified><xsl:value-of select="@ModificationDateTime"/></modified>
    </StopArea>
  </xsl:template>

  <xsl:template name="stop-descriptor">
    <xsl:param name="desc"/>
    <xsl:choose>
      <!-- Set null if no alphanumeric characters or 'none' -->
      <xsl:when test="boolean(re:match($desc, '^[^\w]*$') or func:lower($desc)='none')"/>
      <!-- Capitalise properly if there are no lowercase letters (ie all capitals) -->
      <xsl:when test="not(re:match($desc, '[a-z]'))">
        <xsl:value-of select="func:capitalize($desc)"/>
      </xsl:when>
      <!-- Else pass through -->
      <xsl:otherwise>
        <xsl:value-of select="$desc"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:transform>