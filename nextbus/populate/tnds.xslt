<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:txc="http://www.transxchange.org.uk/"
               xmlns:func="http://nextbus.org/functions" 
               xmlns:exsl="http://exslt.org/common"
               xmlns:re="http://exslt.org/regular-expressions"
               exclude-result-prefixes="func exsl re txc">
  <xsl:output method="xml" indent="yes"/>
  <xsl:param name="region"/>
  <xsl:param name="modified" select="txc:TransXChange/@ModificationDateTime"/>

  <xsl:param name="operators" select="txc:TransXChange/txc:Operators/txc:Operator"/>
  <xsl:param name="services" select="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]"/>
  <xsl:param name="lines" select="$services/txc:Lines/txc:Line"/>
  <xsl:param name="patterns" select="$services/txc:StandardService/txc:JourneyPattern"/>
  <xsl:param name="pattern_sections" select="$patterns/txc:JourneyPatternSectionRefs"/>
  <xsl:param name="sections" select="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection"/>
  <xsl:param name="journey_links" select="$sections/txc:JourneyPatternTimingLink"/>

  <xsl:param name="organisations" select="txc:TransXChange/txc:ServicedOrganisations/txc:ServicedOrganisation"/>
  <xsl:param name="organisation_workings" select="$organisations/txc:WorkingDays/txc:DateRange"/>
  <xsl:param name="organisation_holidays" select="$organisations/txc:Holidays/txc:DateRange"/>
  <xsl:param name="organisation_working_excluded" select="$organisations/txc:WorkingDays/txc:DateExclusion"/>
  <xsl:param name="organisation_holiday_excluded" select="$organisations/txc:Holidays/txc:DateExclusion"/>

  <xsl:param name="vehicle_journeys" select="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney"/>

  <xsl:key name="key_route_links" match="txc:TransXChange/txc:RouteSections/txc:RouteSection/txc:RouteLink" use="@id"/>
  <xsl:key name="key_services" match="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]" use="txc:ServiceCode"/>
  <xsl:key name="key_patterns" match="txc:TransXChange/txc:Services/txc:Service/txc:StandardService/txc:JourneyPattern" use="@id"/>

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
      <modified><xsl:value-of select="$modified"/></modified>
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
      <id><xsl:value-of select="@id"/></id>
      <service_ref><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/></service_ref>
      <direction><xsl:value-of select="txc:Direction"/></direction>
      <modified><xsl:if test="@ModificationDateTime"><xsl:value-of select="@ModificationDateTime"/></xsl:if></modified>
    </JourneyPattern>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternSection">
    <JourneySection>
      <id><xsl:value-of select="@id"/></id>
    </JourneySection>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternSectionRefs">
    <JourneySections>
      <pattern_ref><xsl:value-of select="ancestor::txc:JourneyPattern/@id"/></pattern_ref>
      <section_ref><xsl:value-of select="current()"/></section_ref>
      <sequence><xsl:value-of select="1 + count(preceding-sibling::*)"/></sequence>
    </JourneySections>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternTimingLink">
    <JourneyLink>
      <section_ref><xsl:value-of select="ancestor::txc:JourneyPatternSection/@id"/></section_ref>
      <stop_start><xsl:value-of select="txc:From/txc:StopPointRef"/></stop_start>
      <wait_start><xsl:value-of select="func:convert_duration(txc:From/txc:WaitTime)"/></wait_start>
      <timing_start><xsl:value-of select="txc:From/txc:TimingStatus"/></timing_start>
      <stopping_start>
        <xsl:choose>
          <xsl:when test="txc:To[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping_start>
      <stop_end><xsl:value-of select="txc:To/txc:StopPointRef"/></stop_end>
      <wait_end><xsl:value-of select="func:convert_duration(txc:To/txc:WaitTime)"/></wait_end>
      <timing_end><xsl:value-of select="txc:To/txc:TimingStatus"/></timing_end>
      <stopping_end>
        <xsl:choose>
          <xsl:when test="txc:To[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping_end>
      <run_time><xsl:value-of select="func:convert_duration(txc:RunTime)"/></run_time>
      <direction><xsl:value-of select="txc:Direction"/></direction>
      <route_direction><xsl:value-of select="key('key_route_links', txc:RouteLinkRef)/txc:Direction"/></route_direction>
      <sequence><xsl:value-of select="1 + count(preceding-sibling::*)"/></sequence>
    </JourneyLink>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney">
    <Journey>
      <code><xsl:value-of select="concat(txc:ServiceRef, '-', txc:VehicleJourneyCode)"/></code>
      <service_ref><xsl:value-of select="txc:ServiceRef"/></service_ref>
      <line_ref>
        <xsl:choose>
          <xsl:when test="contains(txc:LineRef, txc:ServiceRef)"><xsl:value-of select="txc:LineRef"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat(txc:ServiceRef, '-', txc:LineRef)"/></xsl:otherwise>
        </xsl:choose>
      </line_ref>
      <pattern_ref><xsl:value-of select="txc:JourneyPatternRef"/></pattern_ref>
      <departure><xsl:value-of select="txc:DepartureTime"/></departure>
      <xsl:call-template name="operating_profile">
        <xsl:with-param name="vj_op" select="txc:OperatingProfile"/>
        <xsl:with-param name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
        <xsl:with-param name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
      </xsl:call-template>
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
        <working>
          <xsl:choose>
            <xsl:when test="ancestor::txc:WorkingDays">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </working>
      </OperatingDate>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="operating_periods">
    <xsl:param name="working"/>
  </xsl:template>

  <xsl:template match="txc:ServicedOrganisation" mode="operating_periods">
    <xsl:for-each select="//txc:DateRange">
      <OperatingPeriod>
        <org_ref><xsl:value-of select="concat($region, ancestor::txc:ServicedOrganisation/txc:OrganisationCode)"/></org_ref>
        <date_start><xsl:value-of select="txc:StartDate"/></date_start>
        <date_end><xsl:value-of select="txc:EndDate"/></date_end>
        <working>
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
      <journey_ref><xsl:value-of select="concat(ancestor::txc:VehicleJourney/txc:ServiceRef, '-', ancestor::txc:VehicleJourney/txc:VehicleJourneyCode)"/></journey_ref>
      <operational><xsl:value-of select="$operational"/></operational>
      <working><xsl:value-of select="$working"/></working>
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
    <xsl:param name="operational"/>
    <SpecialPeriod>
      <journey_ref><xsl:value-of select="concat(ancestor::txc:VehicleJourney/txc:ServiceRef, '-', ancestor::txc:VehicleJourney/txc:VehicleJourneyCode)"/></journey_ref>
      <date_start><xsl:value-of select="txc:StartDate"/></date_start>
      <date_end><xsl:value-of select="txc:EndDate"/></date_end>
      <operational><xsl:value-of select="$operational"/></operational>
    </SpecialPeriod>
  </xsl:template>

  <xsl:template name="sequence_special">
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="special_days">
        <xsl:with-param name="operational">
          <xsl:choose>
            <xsl:when test="ancestor::txc:DaysOfOperation">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </xsl:with-param>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="special_periods">
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="refs" select="txc:OperatingProfile//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="refs" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="key('services', txc:ServiceRef)/txc:OperatingProfile">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="refs" select="key('services', txc:ServiceRef)/txc:OperatingProfile//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="bank_holiday">
    <xsl:param name="operational"/>
    <xsl:param name="holiday" select="false()"/>
    <xsl:choose>
      <xsl:when test="boolean($holiday = 'AllBankHolidays' or current() = 'AllBankHolidays')">
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">AllHolidaysExceptChristmas</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">Christmas</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">DisplacementHolidays</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="boolean($holiday = 'EarlyRunOff' or current() = 'EarlyRunOff')">
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">ChristmasEve</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">NewYearsEve</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="boolean($holiday = 'AllHolidaysExceptChristmas' or current() = 'AllHolidaysExceptChristmas')">
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">NewYearsDay</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">Jan2ndScotland</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">GoodFriday</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="boolean($holiday = 'HolidayMondays' or current() = 'HolidayMondays')">
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">EasterMonday</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">MayDay</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">SpringBank</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">LateSummerHolidayNotScotland</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">AugustBankHolidayScotland</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="boolean($holiday = 'Christmas' or current() = 'Christmas')">
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">ChristmasDay</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">BoxingDay</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="boolean($holiday = 'DisplacementHolidays' or current() = 'DisplacementHolidays')">
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">ChristmasDayHoliday</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">BoxingDayHoliday</xsl:with-param>
        </xsl:call-template>
        <xsl:call-template name="bank_holiday">
          <xsl:with-param name="operational" select="$operational"/>
          <xsl:with-param name="holiday">NewYearsDayHoliday</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <BankHolidays>
          <name>
            <xsl:choose>
              <xsl:when test="$holiday"><xsl:value-of select="holiday"/></xsl:when>
              <xsl:otherwise><xsl:value-of select="local-name(current())"/></xsl:otherwise>
            </xsl:choose>
          </name>
          <journey_ref><xsl:value-of select="concat(ancestor::txc:VehicleJourney/txc:ServiceRef, '-', ancestor::txc:VehicleJourney/txc:VehicleJourneyCode)"/></journey_ref>
          <operational><xsl:value-of select="$operational"/></operational>
        </BankHolidays>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="sequence_bank_holidays">
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="bank_holiday">
        <xsl:with-param name="operational">
          <xsl:choose>
            <xsl:when test="ancestor::txc:DaysOfOperation">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </xsl:with-param>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="bank_holidays">
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="refs" select="txc:OperatingProfile/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="refs" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="key('services', txc:ServiceRef)/txc:OperatingProfile">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="refs" select="key('services', txc:ServiceRef)/txc:OperatingProfile/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="operating_profile">
    <xsl:param name="vj_op"/>
    <xsl:param name="jp_op"/>
    <xsl:param name="s_op"/>
    <xsl:choose>
      <xsl:when test="$vj_op">
        <days><xsl:value-of select="func:days_week($vj_op/txc:RegularDayType)"/></days>
        <weeks><xsl:value-of select="func:weeks_month($vj_op/txc:PeriodicDayType)"/></weeks>
      </xsl:when>
      <xsl:when test="$jp_op">
        <days><xsl:value-of select="func:days_week($jp_op/txc:RegularDayType)"/></days>
        <weeks><weeks><xsl:value-of select="func:weeks_month($jp_op/txc:PeriodicDayType)"/></weeks></weeks>
      </xsl:when>
      <xsl:when test="$s_op">
        <days><xsl:value-of select="func:days_week($s_op/txc:RegularDayType)"/></days>
        <weeks><weeks><xsl:value-of select="func:weeks_month($s_op/txc:PeriodicDayType)"/></weeks></weeks>
      </xsl:when>
      <xsl:otherwise>
        <days><xsl:value-of select="func:days_week()"/></days>
        <weeks/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:transform>