<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:txc="http://www.transxchange.org.uk/"
               xmlns:func="http://nextbus.org/functions" 
               xmlns:exsl="http://exslt.org/common"
               exclude-result-prefixes="xsl func exsl re txc">
  <xsl:output method="xml" indent="yes"/>
  <xsl:param name="region"/>
  <xsl:param name="modified" select="txc:TransXChange/@ModificationDateTime"/>

  <xsl:param name="operators" select="txc:TransXChange/txc:Operators/txc:Operator"/>
  <xsl:param name="services" select="txc:TransXChange/txc:Services/txc:Service[txc:StandardService][txc:Mode[.='underground' or .='metro' or .='bus' or .='tram']]"/>
  <xsl:param name="lines" select="$services/txc:Lines/txc:Line"/>
  <xsl:param name="patterns" select="$services/txc:StandardService/txc:JourneyPattern"/>
  <xsl:param name="pattern_sections" select="$patterns/txc:JourneyPatternSectionRefs"/>
  <xsl:param name="sections" select="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection"/>
  <xsl:param name="journey_links" select="$sections/txc:JourneyPatternTimingLink"/>

  <xsl:param name="organisations" select="txc:TransXChange/txc:ServicedOrganisations/txc:ServicedOrganisation"/>

  <xsl:param name="vehicle_journeys" select="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney"/>

  <xsl:key name="key_operators" match="txc:TransXChange/txc:Operators/txc:Operator" use="@id"/>
  <xsl:key name="key_route_links" match="txc:TransXChange/txc:RouteSections/txc:RouteSection/txc:RouteLink" use="@id"/>
  <xsl:key name="key_services" match="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]" use="txc:ServiceCode"/>
  <xsl:key name="key_patterns" match="txc:TransXChange/txc:Services/txc:Service/txc:StandardService/txc:JourneyPattern" use="@id"/>
  <xsl:key name="key_pattern_sections" match="txc:TransXChange/txc:Services/txc:Service/txc:StandardService/txc:JourneyPattern/txc:JourneyPatternSectionRefs" use="."/>

  <xsl:template match="txc:TransXChange">
    <Data>
      <xsl:if test="boolean($services)">
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
        </JourneyLinkGroup>
        <JourneyGroup>
          <xsl:apply-templates select="$vehicle_journeys"/>
        </JourneyGroup>
        <OrganisationGroup>
          <xsl:apply-templates select="$organisations"/>
        </OrganisationGroup>
        <OperatingDateGroup>
          <xsl:apply-templates select="$organisations" mode="excluded_days"/>
        </OperatingDateGroup>
        <OperatingPeriodGroup>
          <xsl:apply-templates select="$organisations" mode="operating_periods"/>
        </OperatingPeriodGroup>
        <OrganisationsGroup>
          <xsl:apply-templates select="$vehicle_journeys" mode="organisations_served"/>
        </OrganisationsGroup>
        <SpecialPeriodGroup>
          <xsl:apply-templates select="$vehicle_journeys" mode="special_periods"/>
        </SpecialPeriodGroup>
        <BankHolidaysGroup>
          <xsl:apply-templates select="$vehicle_journeys" mode="bank_holidays"/>
        </BankHolidaysGroup>
      </xsl:if>
    </Data>
  </xsl:template>

  <xsl:template match="txc:Operator" mode="national">
    <Operator>
      <code><xsl:value-of select="txc:NationalOperatorCode"/></code>
    </Operator>
  </xsl:template>

  <xsl:template match="txc:Operator" mode="local">
    <LocalOperator>
      <operator_ref><xsl:value-of select="txc:NationalOperatorCode"/></operator_ref>
      <region_ref><xsl:value-of select="$region"/></region_ref>
      <code><xsl:value-of select="txc:OperatorCode"/></code>
      <name><xsl:value-of select="txc:OperatorShortName"/></name>
    </LocalOperator>
  </xsl:template>

  <xsl:template match="txc:Service">
    <Service>
      <code><xsl:value-of select="txc:ServiceCode"/></code>
      <origin><xsl:value-of select="txc:StandardService/txc:Origin"/></origin>
      <destination><xsl:value-of select="txc:StandardService/txc:Destination"/></destination>
      <date_start><xsl:value-of select="txc:OperatingPeriod/txc:StartDate"/></date_start>
      <date_end><xsl:value-of select="txc:OperatingPeriod/txc:EndDate"/></date_end>
      <local_operator_ref><xsl:value-of select="key('key_operators', txc:RegisteredOperatorRef)/txc:OperatorCode"/></local_operator_ref>
      <region_ref><xsl:value-of select="$region"/></region_ref>
      <mode>
        <xsl:choose>
          <xsl:when test="boolean(txc:Mode = 'underground')">metro</xsl:when>
          <xsl:otherwise><xsl:value-of select="txc:Mode"/></xsl:otherwise>
        </xsl:choose>
      </mode>
      <direction>
        <xsl:choose>
          <xsl:when test="txc:Direction"><xsl:value-of select="txc:Direction"/></xsl:when>
          <xsl:otherwise>outbound</xsl:otherwise>
        </xsl:choose>
      </direction>
      <modified py_type="datetime"><xsl:value-of select="$modified"/></modified>
    </Service>
  </xsl:template>

  <xsl:template match="txc:Line">
    <ServiceLine>
      <id>
        <xsl:choose>
          <xsl:when test="contains(@id, ancestor::txc:Service/txc:ServiceCode)"><xsl:value-of select="@id"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(ancestor::txc:Service/txc:ServiceCode, '-', @id)"/></xsl:otherwise>
        </xsl:choose>
      </id>
      <name><xsl:value-of select="txc:LineName"/></name>
      <service_ref><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/></service_ref>
    </ServiceLine>
  </xsl:template>

  <xsl:template match="txc:JourneyPattern">
    <JourneyPattern>
      <id>
        <xsl:choose>
          <xsl:when test="contains(@id, ancestor::txc:Service/txc:ServiceCode)"><xsl:value-of select="@id"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(ancestor::txc:Service/txc:ServiceCode, '-', @id)"/></xsl:otherwise>
        </xsl:choose>
      </id>
      <service_ref><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/></service_ref>
      <direction><xsl:value-of select="txc:Direction"/></direction>
      <modified py_type="datetime"><xsl:if test="@ModificationDateTime"><xsl:value-of select="@ModificationDateTime"/></xsl:if></modified>
    </JourneyPattern>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternSection">
    <JourneySection>
      <id>
        <xsl:choose>
          <xsl:when test="contains(@id, key('key_pattern_sections', @id)/ancestor::txc:Service/txc:ServiceCode)"><xsl:value-of select="@id"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(key('key_pattern_sections', @id)/ancestor::txc:Service/txc:ServiceCode, '-', @id)"/></xsl:otherwise>
        </xsl:choose>
      </id>
    </JourneySection>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternSectionRefs">
    <JourneySections>
      <xsl:variable name="jp_id" select="ancestor::txc:JourneyPattern/@id"/>
      <pattern_ref>
        <xsl:choose>
          <xsl:when test="contains($jp_id, ancestor::txc:Service/txc:ServiceCode)"><xsl:value-of select="$jp_id"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(ancestor::txc:Service/txc:ServiceCode, '-', $jp_id)"/></xsl:otherwise>
        </xsl:choose>
      </pattern_ref>
      <section_ref>
        <xsl:choose>
          <xsl:when test="contains(current(), ancestor::txc:Service/txc:ServiceCode)"><xsl:value-of select="current()"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(ancestor::txc:Service/txc:ServiceCode, '-', current())"/></xsl:otherwise>
        </xsl:choose>
      </section_ref>
      <sequence><xsl:value-of select="count(preceding-sibling::txc:JourneyPatternSectionRefs)"/></sequence>
    </JourneySections>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternTimingLink">
    <xsl:variable name="jp_id" select="ancestor::txc:JourneyPatternSection/@id"/>
    <xsl:variable name="jp_ref" select="key('key_pattern_sections', $jp_id)"/>
    <xsl:variable name="s_ref" select="$jp_ref/ancestor::txc:Service/txc:ServiceCode"/>
    <JourneyLink>
      <section_ref>
        <xsl:choose>
          <xsl:when test="contains($jp_id, $s_ref)"><xsl:value-of select="$jp_id"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat($s_ref, '-', $jp_id)"/></xsl:otherwise>
        </xsl:choose>
      </section_ref>
      <stop_start><xsl:value-of select="txc:From/txc:StopPointRef"/></stop_start>
      <wait_start py_type="duration">
        <xsl:choose>
          <xsl:when test="txc:From/txc:WaitTime"><xsl:value-of select="txc:From/txc:WaitTime"/></xsl:when>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_start>
      <timing_start><xsl:value-of select="txc:From/txc:TimingStatus"/></timing_start>
      <stopping_start py_type="bool">
        <xsl:choose>
          <xsl:when test="txc:From[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping_start>
      <stop_end><xsl:value-of select="txc:To/txc:StopPointRef"/></stop_end>
      <wait_end py_type="duration">
        <xsl:choose>
          <xsl:when test="txc:To/txc:WaitTime"><xsl:value-of select="txc:To/txc:WaitTime"/></xsl:when>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_end>
      <timing_end><xsl:value-of select="txc:To/txc:TimingStatus"/></timing_end>
      <stopping_end py_type="bool">
        <xsl:choose>
          <xsl:when test="txc:To[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping_end>
      <run_time py_type="duration"><xsl:value-of select="txc:RunTime"/></run_time>
      <direction><xsl:value-of select="txc:Direction"/></direction>
      <route_direction><xsl:value-of select="key('key_route_links', txc:RouteLinkRef)/txc:Direction"/></route_direction>
      <sequence><xsl:value-of select="count(preceding-sibling::txc:JourneyPatternTimingLink)"/></sequence>
    </JourneyLink>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney">
    <xsl:variable name="jp" select="key('key_patterns', txc:JourneyPatternRef)"/>
    <xsl:variable name="jp_op" select="$jp/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <Journey>
      <code><xsl:value-of select="concat($region, txc:VehicleJourneyCode)"/></code>
      <service_ref><xsl:value-of select="txc:ServiceRef"/></service_ref>
      <line_ref>
        <xsl:choose>
          <xsl:when test="contains(txc:LineRef, txc:ServiceRef)"><xsl:value-of select="txc:LineRef"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(txc:ServiceRef, '-', txc:LineRef)"/></xsl:otherwise>
        </xsl:choose>
      </line_ref>
      <pattern_ref>
        <xsl:choose>
          <xsl:when test="contains(txc:JourneyPatternRef, $jp/ancestor::txc:Service/txc:ServiceCode)"><xsl:value-of select="txc:JourneyPatternRef"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat($jp/ancestor::txc:Service/txc:ServiceCode, '-', txc:JourneyPatternRef)"/></xsl:otherwise>
        </xsl:choose>
      </pattern_ref>
      <departure><xsl:value-of select="txc:DepartureTime"/></departure>
      <xsl:choose>
        <xsl:when test="txc:OperatingProfile">
          <days><xsl:value-of select="func:days_week(txc:OperatingProfile/txc:RegularDayType)"/></days>
          <weeks><xsl:value-of select="func:weeks_month(txc:OperatingProfile/txc:PeriodicDayType)"/></weeks>
        </xsl:when>
        <xsl:when test="$jp_op">
          <days><xsl:value-of select="func:days_week($jp_op/txc:RegularDayType)"/></days>
          <weeks><xsl:value-of select="func:weeks_month($jp_op/txc:PeriodicDayType)"/></weeks>
        </xsl:when>
        <xsl:when test="$s_op">
          <days><xsl:value-of select="func:days_week($s_op/txc:RegularDayType)"/></days>
          <weeks><xsl:value-of select="func:weeks_month($s_op/txc:PeriodicDayType)"/></weeks>
        </xsl:when>
        <xsl:otherwise>
          <days><xsl:value-of select="func:days_week()"/></days>
          <weeks/>
        </xsl:otherwise>
      </xsl:choose>
    </Journey>
  </xsl:template>

  <xsl:template match="txc:ServicedOrganisation">
    <Organisation>
      <code><xsl:value-of select="concat($region, txc:OrganisationCode)"/></code>
    </Organisation>
  </xsl:template>

  <xsl:template match="txc:ServicedOrganisation" mode="excluded_days">
    <xsl:for-each select="//txc:DateExclusion">
      <OperatingDate>
        <org_ref><xsl:value-of select="concat($region, ancestor::txc:ServicedOrganisation/txc:OrganisationCode)"/></org_ref>
        <date><xsl:value-of select="current()"/></date>
        <working py_type="bool">
          <xsl:choose>
            <xsl:when test="ancestor::txc:WorkingDays">0</xsl:when>
            <xsl:otherwise>1</xsl:otherwise>
          </xsl:choose>
        </working>
      </OperatingDate>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="operating_periods">
    <xsl:param name="working"/>
  </xsl:template>

  <xsl:template match="txc:ServicedOrganisation" mode="operating_periods">
    <xsl:for-each select=".//txc:DateRange">
      <OperatingPeriod>
        <org_ref><xsl:value-of select="concat($region, ancestor::txc:ServicedOrganisation/txc:OrganisationCode)"/></org_ref>
        <date_start><xsl:value-of select="txc:StartDate"/></date_start>
        <date_end><xsl:value-of select="txc:EndDate"/></date_end>
        <working py_type="bool">
          <xsl:choose>
            <xsl:when test="ancestor::txc:WorkingDays">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </working>
      </OperatingPeriod>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="organisation_days">
    <xsl:param name="operational"/>
    <xsl:param name="working"/>
    <Organisations>
      <org_ref><xsl:value-of select="concat($region, current())"/></org_ref>
      <journey_ref><xsl:value-of select="concat($region, ancestor::txc:VehicleJourney/txc:VehicleJourneyCode)"/></journey_ref>
      <operational py_type="bool"><xsl:value-of select="$operational"/></operational>
      <working py_type="bool"><xsl:value-of select="$working"/></working>
    </Organisations>
  </xsl:template>

  <xsl:template name="sequence_organisation_days">
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="organisation_days">
        <xsl:with-param name="operational">
          <xsl:choose>
            <xsl:when test="ancestor::txc:DaysOfOperation">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </xsl:with-param>
        <xsl:with-param name="working">
          <xsl:choose>
            <xsl:when test="ancestor::txc:WorkingDays">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </xsl:with-param>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="organisations_served">
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="key('services', txc:ServiceRef)/txc:OperatingProfile">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="key('services', txc:ServiceRef)/txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="special_days">
    <xsl:param name="code"/>
    <SpecialPeriod>
      <journey_ref><xsl:value-of select="$code"/></journey_ref>
      <date_start><xsl:value-of select="txc:StartDate"/></date_start>
      <date_end><xsl:value-of select="txc:EndDate"/></date_end>
      <operational py_type="bool">
        <xsl:choose>
          <xsl:when test="ancestor::txc:DaysOfOperation">1</xsl:when>
          <xsl:otherwise>0</xsl:otherwise>
        </xsl:choose>
      </operational>
    </SpecialPeriod>
  </xsl:template>

  <xsl:template name="sequence_special">
    <xsl:param name="code"/>
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="special_days">
        <xsl:with-param name="code" select="$code"/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="special_periods">
    <xsl:variable name="code" select="concat($region, txc:VehicleJourneyCode)"/>
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="code" select="$code"/>
          <xsl:with-param name="refs" select="txc:OperatingProfile//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$jp_op">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="code" select="$code"/>
          <xsl:with-param name="refs" select="$jp_op//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$s_op">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="code" select="$code"/>
          <xsl:with-param name="refs" select="$s_op//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="bank_holiday_group">
    <xsl:param name="code">0</xsl:param>
    <xsl:variable name="holiday" select="local-name()"/>
    <xsl:variable name="holidays">
      <xsl:choose>
        <xsl:when test="boolean($holiday = 'AllBankHolidays')">
          <holiday>NewYearsDay</holiday>
          <xsl:if test="boolean($region = 'S')">
            <holiday>Jan2ndScotland</holiday>
          </xsl:if>
          <holiday>GoodFriday</holiday>
          <holiday>EasterMonday</holiday>
          <holiday>MayDay</holiday>
          <holiday>SpringBank</holiday>
          <xsl:if test="boolean($region = 'S')">
            <holiday>AugustBankHolidayScotland</holiday>
          </xsl:if>
          <xsl:if test="boolean($region != 'S')">
            <holiday>LateSummerBankHolidayNotScotland</holiday>
          </xsl:if>
          <holiday>ChristmasDay</holiday>
          <holiday>BoxingDay</holiday>
          <holiday>ChristmasDayHoliday</holiday>
          <holiday>BoxingDayHoliday</holiday>
          <holiday>NewYearsDayHoliday</holiday>
        </xsl:when>
        <xsl:when test="boolean($holiday = 'EarlyRunOff')">
          <holiday>ChristmasEve</holiday>
          <holiday>NewYearsEve</holiday>
        </xsl:when>
        <xsl:when test="boolean($holiday = 'AllHolidaysExceptChristmas')">
          <holiday>NewYearsDay</holiday>
          <xsl:if test="boolean($region = 'S')">
            <holiday>Jan2ndScotland</holiday>
          </xsl:if>
          <holiday>GoodFriday</holiday>
          <holiday>EasterMonday</holiday>
          <holiday>MayDay</holiday>
          <holiday>SpringBank</holiday>
          <xsl:if test="boolean($region = 'S')">
            <holiday>AugustBankHolidayScotland</holiday>
          </xsl:if>
          <xsl:if test="boolean($region != 'S')">
            <holiday>LateSummerBankHolidayNotScotland</holiday>
          </xsl:if>
        </xsl:when>
        <xsl:when test="boolean($holiday = 'HolidayMondays')">
          <holiday>EasterMonday</holiday>
          <holiday>MayDay</holiday>
          <holiday>SpringBank</holiday>
          <xsl:if test="boolean($region = 'S')">
            <holiday>AugustBankHolidayScotland</holiday>
          </xsl:if>
          <xsl:if test="boolean($region != 'S')">
            <holiday>LateSummerBankHolidayNotScotland</holiday>
          </xsl:if>
        </xsl:when>
        <xsl:when test="boolean($holiday = 'Christmas')">
          <holiday>ChristmasDay</holiday>
          <holiday>BoxingDay</holiday>
        </xsl:when>
        <xsl:when test="boolean($holiday = 'DisplacementHolidays')">
          <holiday>ChristmasDayHoliday</holiday>
          <holiday>BoxingDayHoliday</holiday>
          <holiday>NewYearsDayHoliday</holiday>
        </xsl:when>
        <xsl:otherwise>
          <holiday/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="operational">
      <xsl:choose>
        <xsl:when test="ancestor::txc:DaysOfOperation">1</xsl:when>
        <xsl:otherwise>0</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:for-each select="exsl:node-set($holidays)/holiday">
      <BankHolidays>
        <name>
          <xsl:choose>
            <xsl:when test="current()/text()"><xsl:value-of select="current()"/></xsl:when>
            <xsl:otherwise><xsl:value-of select="$holiday"/></xsl:otherwise>
          </xsl:choose>
        </name>
        <journey_ref><xsl:value-of select="$code"/></journey_ref>
        <operational py_type="bool"><xsl:value-of select="$operational"/></operational>
      </BankHolidays>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="sequence_bank_holidays">
    <xsl:param name="code"/>
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="bank_holiday_group">
        <xsl:with-param name="code" select="$code"/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="bank_holidays">
    <xsl:variable name="code" select="concat($region, txc:VehicleJourneyCode)"/>
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="code" select="$code"/>
          <xsl:with-param name="refs" select="txc:OperatingProfile/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$jp_op">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="code" select="$code"/>
          <xsl:with-param name="refs" select="$jp_op/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$s_op">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="code" select="$code"/>
          <xsl:with-param name="refs" select="$s_op/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>
</xsl:transform>