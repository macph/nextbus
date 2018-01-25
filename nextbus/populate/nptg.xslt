<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:n="http://www.naptan.org.uk/"
               xmlns:f="http://nextbus.org/functions"
               exclude-result-prefixes="f">
  <xsl:output method="xml" indent="yes"/>
  <xsl:param name="regions" select="n:NationalPublicTransportGazetteer/n:Regions/n:Region"/>
  <xsl:param name="areas" select="n:NationalPublicTransportGazetteer/n:Regions//n:AdministrativeArea"/>
  <xsl:param name="districts" select="n:NationalPublicTransportGazetteer/n:Regions//n:NptgDistrict"/>
  <xsl:param name="localities" select="n:NationalPublicTransportGazetteer/n:NptgLocalities/n:NptgLocality"/>

  <xsl:template match="n:NationalPublicTransportGazetteer">
    <Data>
      <Regions>
        <xsl:apply-templates select="$regions"/>
      </Regions>
      <AdminAreas>
        <xsl:apply-templates select="$areas"/>
      </AdminAreas>
      <Districts>
        <xsl:apply-templates select="$districts"/>
      </Districts>
      <Localities>
        <xsl:apply-templates select="$localities"/>
      </Localities>
    </Data>
  </xsl:template>

  <xsl:template match="n:Region">
    <Region>
      <code><xsl:value-of select="f:upper(n:RegionCode)"/></code>
      <name><xsl:value-of select="n:Name"/></name>
      <modified><xsl:value-of select="@ModificationDateTime"/></modified>
    </Region>
  </xsl:template>

  <xsl:template match="n:AdministrativeArea">
    <AdminArea>
      <code><xsl:value-of select="n:AdministrativeAreaCode"/></code>
      <region_code><xsl:value-of select="ancestor::n:Region/n:RegionCode"/></region_code>
      <atco_code><xsl:value-of select="n:AtcoAreaCode"/></atco_code>
      <name><xsl:value-of select="n:Name"/></name>
      <modified><xsl:value-of select="@ModificationDateTime"/></modified>
    </AdminArea>
  </xsl:template>

  <xsl:template match="n:NptgDistrict">
    <District>
      <code><xsl:value-of select="n:NptgDistrictCode"/></code>
      <admin_area_code>
        <xsl:value-of select="ancestor::n:AdministrativeArea/n:AdministrativeAreaCode"/>
      </admin_area_code>
      <name><xsl:value-of select="n:Name"/></name>
      <modified><xsl:value-of select="@ModificationDateTime"/></modified>
    </District>
  </xsl:template>

  <xsl:template match="n:NptgLocality">
    <Locality>
      <code><xsl:value-of select="f:upper(n:NptgLocalityCode)"/></code>
      <name><xsl:value-of select="n:Descriptor/n:LocalityName"/></name>
      <parent_code><xsl:value-of select="f:upper(n:ParentNptgLocalityRef)"/></parent_code>
      <admin_area_code><xsl:value-of select="n:AdministrativeAreaRef"/></admin_area_code>
      <district_code>
        <xsl:choose>
          <!-- Ignore district code if it equals 310 -->
          <xsl:when test="not(n:NptgDistrictRef='310')">
            <xsl:value-of select="n:NptgDistrictRef"/>
          </xsl:when>
          <xsl:otherwise/>
        </xsl:choose>
      </district_code>
      <easting><xsl:value-of select="n:Location/n:Translation/n:Easting"/></easting>
      <northing><xsl:value-of select="n:Location/n:Translation/n:Northing"/></northing>
      <longitude><xsl:value-of select="n:Location/n:Translation/n:Longitude"/></longitude>
      <latitude><xsl:value-of select="n:Location/n:Translation/n:Latitude"/></latitude>
      <modified><xsl:value-of select="@ModificationDateTime"/></modified>
    </Locality>
  </xsl:template>

  <xsl:template match="n:PlusbusZones"/>
</xsl:transform>