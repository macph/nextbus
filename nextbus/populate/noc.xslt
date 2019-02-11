<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:exsl="http://exslt.org/common"
               xmlns:func="http://nextbus.org/functions"
               exclude-result-prefixes="xsl exsl func">
  <xsl:output method="xml" indent="yes"/>

  <xsl:param name="table" select="travelinedata/NOCTable/NOCTableRecord"/>
  <xsl:param name="lines" select="travelinedata/NOCLines/NOCLinesRecord"/>
  <xsl:param name="regions">
    <region nptg_code="GB"/>
    <region nptg_code="GB">Admin</region>
    <region nptg_code="GB">ADMIN</region>
    <region nptg_code="L">L</region>
    <region nptg_code="L">LO</region>
    <region nptg_code="SW">SW</region>
    <region nptg_code="WM">WM</region>
    <region nptg_code="W">W</region>
    <region nptg_code="W">WA</region>
    <region nptg_code="Y">Y</region>
    <region nptg_code="Y">YO</region>
    <region nptg_code="NW">NW</region>
    <region nptg_code="NE">NE</region>
    <region nptg_code="S">S</region>
    <region nptg_code="S">SC</region>
    <region nptg_code="SE">SE</region>
    <region nptg_code="EA">EA</region>
    <region nptg_code="EM">EM</region>
  </xsl:param>
  <xsl:param name="mode_ids">
    <mode id="1">Bus</mode>
    <mode id="1">CT</mode>
    <mode id="1">CT Operator</mode>
    <mode id="1">DRT</mode>
    <mode id="1">Partly DRT</mode>
    <mode id="1">Permit</mode>
    <mode id="1">Taxi</mode>
    <mode id="2">Coach</mode>
    <mode id="3">Tram</mode>
    <mode id="4">Metro</mode>
    <mode id="5">Underground</mode>
  </xsl:param>
  <xsl:param name="set_regions" select="exsl:node-set($regions)"/>
  <xsl:param name="set_mode_ids" select="exsl:node-set($mode_ids)"/>

  <xsl:key name="key_lines" match="travelinedata/NOCLines/NOCLinesRecord" use="NOCCODE"/>
  <xsl:key name="key_public_name" match="travelinedata/PublicName/PublicNameRecord" use="PubNmId"/>

  <xsl:template match="travelinedata">
    <Data>
      <xsl:apply-templates select="$table"/>
      <xsl:apply-templates select="$lines"/>
    </Data>
  </xsl:template>

  <xsl:template match="NOCTableRecord">
    <xsl:variable name="line" select="key('key_lines', NOCCODE)"/>
    <xsl:variable name="mode_id" select="$set_mode_ids/mode[. = $line/Mode]/@id"/>
    <xsl:if test="$line and $mode_id">
      <Operator>
        <code><xsl:value-of select="NOCCODE"/></code>
        <region_ref><xsl:value-of select="$set_regions/region[. = $line/TLRegOwn]/@nptg_code"/></region_ref>
        <name><xsl:value-of select="OperatorPublicName"/></name>
        <licence_name><xsl:value-of select="VOSA_PSVLicenseName"/></licence_name>
        <mode><xsl:value-of select="$mode_id"/></mode>
        <email><xsl:value-of select="key('key_public_name', PubNmId)/TTRteEnq"/></email>
        <address><xsl:value-of select="key('key_public_name', PubNmId)/ComplEnq"/></address>
        <website>
          <xsl:if test="key('key_public_name', PubNmId)/Website != ''">
            <xsl:value-of select="func:format_website(key('key_public_name', PubNmId)/Website)"/>
          </xsl:if>
        </website>
        <twitter><xsl:value-of select="key('key_public_name', PubNmId)/Twitter"/></twitter>
      </Operator>
    </xsl:if>
  </xsl:template>

  <xsl:template match="NOCLinesRecord">
    <xsl:variable name="line" select="."/>
    <xsl:variable name="mode_id" select="$set_mode_ids/mode[. = $line/Mode]/@id"/>
    <xsl:if test="$mode_id">
      <xsl:for-each select="$set_regions/region">
        <xsl:variable name="region" select="."/>
        <xsl:variable name="local_code" select="$line/*[$region = local-name()]"/>
        <xsl:if test="$local_code and $local_code != ''">
          <LocalOperator>
            <code><xsl:value-of select="$local_code"/></code>
            <region_ref><xsl:value-of select="@nptg_code"/></region_ref>
            <operator_ref><xsl:value-of select="$line/NOCCODE"/></operator_ref>
            <name><xsl:value-of select="$line/PubNm"/></name>
          </LocalOperator>
        </xsl:if>
      </xsl:for-each>
    </xsl:if>
  </xsl:template>
</xsl:transform>