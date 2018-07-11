<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:txc="http://www.transxchange.org.uk/"
               xmlns:func="http://nextbus.org/functions" 
               xmlns:exsl="http://exslt.org/common"
               xmlns:re="http://exslt.org/regular-expressions"
               exclude-result-prefixes="func exsl re txc">
  <xsl:output method="xml" indent="yes"/>
  <xsl:param name="region">Y</xsl:param>
  <xsl:param name="operators" select="txc:TransXChange/txc:Operators/txc:Operator"/>
  <xsl:param name="services" select="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]"/>
  <xsl:param name="lines" select="$services/txc:Lines/txc:Line"/>
  <xsl:param name="patterns" select="$services/txc:StandardService/txc:JourneyPattern"/>
  <xsl:param name="pattern_sections" select="$patterns/txc:JourneyPatternSectionRefs"/>
  <xsl:param name="sections" select="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection"/>
  <xsl:param name="journey_links" select="$sections/txc:JourneyPatternTimingLink"/><!--
  <xsl:param name="route_links" select="txc:TransXChange/txc:RouteSections/txc:RouteSection/txc:RouteLink"/>
  <xsl:param name="organisations" select="txc:TransXChange/txc:ServicedOrganisations/txc:ServicedOrganisation"/>
  <xsl:param name="organisation_workings" select="$organisations/txc:WorkingDays/txc:DateRange"/>
  <xsl:param name="organisation_holidays" select="$organisations/txc:Holidays/txc:DateExclusion"/>
  <xsl:param name="organisation_working_excluded" select="$organisations/txc:WorkingDays/txc:DateRange"/>
  <xsl:param name="organisation_holiday_excluded" select="$organisations/txc:Holidays/txc:DateExclusion"/>
  <xsl:param name="vehicle_journeys" select="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney"/>
  <xsl:param name="special_days_on" select="$vehicle_journeys/txc:OperatingProfile/txc:SpecialDaysOperation/txc:DaysOfOperation"/>
  <xsl:param name="special_days_off" select="$vehicle_journeys/txc:OperatingProfile/txc:SpecialDaysOperation/txc:DaysOfNonOperation"/>
  <xsl:param name="bank_holidays_on" select="$vehicle_journeys/txc:OperatingProfile/txc:BankHolidayOperation/txc:DaysOfNonOperation"/>
  <xsl:param name="bank_holidays_off" select="$vehicle_journeys/txc:OperatingProfile/txc:BankHolidayOperation/txc:DaysOfNonOperation"/>-->

  <xsl:template match="txc:TransXChange">
    <Data>
      <OperatorGroup>
        <xsl:apply-templates select="$operators" mode="national"/>
      </OperatorGroup>
      <LocalOperatorGroup>
        <xsl:apply-templates select="$operators" mode="local"/>
      </LocalOperatorGroup>
      <ServiceGroup>
        <xsl:apply-templates select="$services"/>
      </ServiceGroup>
      <ServiceLineGroup>
        <xsl:apply-templates select="$lines"/>
      </ServiceLineGroup>
      <JourneyPatternGroup>
        <xsl:apply-templates select="$patterns"/>
      </JourneyPatternGroup>
      <JourneySectionsGroup>
        <xsl:apply-templates select="$pattern_sections"/>
      </JourneySectionsGroup>
      <JourneySectionGroup>
        <xsl:apply-templates select="$sections"/>
      </JourneySectionGroup>
      <JourneyLinkGroup>
        <xsl:apply-templates select="$journey_links"/>
      </JourneyLinkGroup><!--
      <OperatingDateGroup>
        <xsl:apply-templates select="$organisation_working_excluded"/>
        <xsl:apply-templates select="$organisation_holiday_excluded"/>
      </OperatingDateGroup>
      <OperatingPeriodGroup>
        <xsl:apply-templates select="$organisation_workings"/>
        <xsl:apply-templates select="$organisation_holidays"/>
      </OperatingPeriodGroup>
      <OrganisationGroup>
        <xsl:apply-templates select="$organsiations" mode="single"/>
      </OrganisationGroup>
      <OrganisationsGroup>
        <xsl:apply-templates select="$organsiations" mode="multiple"/>
      </OrganisationsGroup>
      <SpecialPeriodGroup>
        <xsl:apply-templates select="$special_days_on"/>
        <xsl:apply-templates select="$special_days_off"/>
      </SpecialPeriodGroup>
      <BankHolidaysGroup>
        <xsl:apply-templates select="$bank_holidays_on"/>
        <xsl:apply-templates select="$bank_holidays_off"/>
      </BankHolidaysGroup>
      <JourneyGroup>
        <xsl:apply-templates select="$vehicle_journeys"/>
      </JourneyGroup>-->
    </Data>
  </xsl:template>

  <xsl:template match="txc:Operator" mode="national">
    <Operator>
      <code><xsl:value-of select="func:upper(txc:NationalOperatorCode)"/></code>
      <name><xsl:value-of select="txc:OperatorShortName"/></name>
    </Operator>
  </xsl:template>

  <xsl:template match="txc:Operator" mode="local">
    <LocalOperator>
      <operator_ref><xsl:value-of select="func:upper(txc:NationalOperatorCode)"/></operator_ref>
      <region_ref><xsl:value-of select="$region"/></region_ref>
      <code><xsl:value-of select="func:upper(txc:OperatorCode)"/></code>
    </LocalOperator>
  </xsl:template>

  <xsl:template match="txc:Service">
    <Service>
      <code><xsl:value-of select="func:upper(txc:ServiceCode)"/></code>
      <origin><xsl:value-of select="txc:StandardService/txc:Origin"/></origin>
      <destination><xsl:value-of select="txc:StandardService/txc:Destination"/></destination>
      <date_start><xsl:value-of select="txc:OperatingPeriod/txc:StartDate"/></date_start>
      <date_end><xsl:value-of select="txc:OperatingPeriod/txc:EndDate"/></date_end>
      <local_operator_ref><xsl:value-of select="txc:RegisteredOperatorRef"/></local_operator_ref>
      <region_ref><xsl:value-of select="$region"/></region_ref>
      <mode><xsl:value-of select="txc:Mode"/></mode>
      <direction>
        <xsl:choose>
          <xsl:when test="txc:Direction"><xsl:value-of select="txc:Direction"/></xsl:when>
          <xsl:otherwise>outbound</xsl:otherwise>
        </xsl:choose>
      </direction>
      <availability>
        <xsl:choose>
          <xsl:when test="txc:ServiceAvailability"><xsl:value-of select="txc:ServiceAvailability"/></xsl:when>
          <xsl:otherwise>daytime</xsl:otherwise>
        </xsl:choose>
      </availability>
      <modified><xsl:if test="@ModificationDateTime"><xsl:value-of select="@ModificationDateTime"/></xsl:if></modified>
    </Service>
  </xsl:template>

  <xsl:template match="txc:Line">
    <ServiceLine>
      <id><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/>-<xsl:value-of select="@id"/></id>
      <name><xsl:value-of select="txc:LineName"/></name>
      <service_ref><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/></service_ref>
    </ServiceLine>
  </xsl:template>

  <xsl:template match="txc:JourneyPattern">
    <JourneyPattern>
      <id><xsl:value-of select="@id"/></id>
      <service_ref><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/></service_ref>
      <modified><xsl:if test="@ModificationDateTime"><xsl:value-of select="@ModificationDateTime"/></xsl:if></modified>
    </JourneyPattern>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternSectionRefs">
    <JourneySections>
      <pattern_ref><xsl:value-of select="current()"/></pattern_ref>
      <section_ref><xsl:value-of select="ancestor::txc:JourneyPattern/@id"/></section_ref>
      <sequence><xsl:value-of select="1 + count(preceding-sibling::*)"/></sequence>
    </JourneySections>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternSection">
    <JourneySection>
      <id><xsl:value-of select="@id"/></id>
    </JourneySection>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternTimingLink">
    <JourneyLink>
      <section_ref><xsl:value-of select="ancestor::txc:JourneyPatternSection/@id"/></section_ref>
      <stop_start><xsl:value-of select="txc:From/txc:StopPointRef"/></stop_start>
      <wait_start><xsl:value-of select="txc:From/txc:WaitTime"/></wait_start>
      <timing_start><xsl:value-of select="txc:From/txc:TimingStatus"/></timing_start>
      <stopping_start>
        <xsl:choose>
          <xsl:when test="txc:From[txc:Activity and txc:Activity[.!='pass']]">1</xsl:when>
          <xsl:otherwise>0</xsl:otherwise>
        </xsl:choose>
      </stopping_start>
      <stop_end><xsl:value-of select="txc:To/txc:StopPointRef"/></stop_end>
      <wait_end><xsl:value-of select="txc:To/txc:WaitTime"/></wait_end>
      <timing_end><xsl:value-of select="txc:To/txc:TimingStatus"/></timing_end>
      <stopping_end>
        <xsl:choose>
          <xsl:when test="txc:To[txc:Activity and txc:Activity[.!='pass']]">1</xsl:when>
          <xsl:otherwise>0</xsl:otherwise>
        </xsl:choose>
      </stopping_end>
      <run_time><xsl:value-of select="txc:RunTime"/></run_time>
      <direction><xsl:value-of select="txc:Direction"/></direction>
      <reverse></reverse>
      <sequence><xsl:value-of select="1 + count(preceding-sibling::*)"/></sequence>
    </JourneyLink>
  </xsl:template>
</xsl:transform>