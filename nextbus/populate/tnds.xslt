<?xml version="1.0" encoding="utf-8"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:txc="http://www.transxchange.org.uk/"
               xmlns:func="http://nextbus.org/functions" 
               xmlns:exsl="http://exslt.org/common"
               exclude-result-prefixes="xsl func exsl re txc">
  <xsl:output method="xml" indent="yes"/>
  <xsl:param name="region"/>
  <xsl:param name="file"/>

  <xsl:param name="operators" select="txc:TransXChange/txc:Operators/txc:Operator"/>
  <xsl:param name="services" select="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]
    [txc:Mode[.='underground' or .='metro' or .='bus' or .='tram']]"/>
  <xsl:param name="patterns" select="$services/txc:StandardService/txc:JourneyPattern"/>
  <xsl:param name="journey_links" select="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection/txc:JourneyPatternTimingLink"/>

  <xsl:param name="organisations" select="txc:TransXChange/txc:ServicedOrganisations/txc:ServicedOrganisation"/>

  <xsl:param name="vehicle_journeys" select="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney"/>

  <xsl:param name="bank_holiday_ids">
    <holiday id="1">NewYearsDay</holiday>
    <holiday id="2">Jan2ndScotland</holiday>
    <holiday id="3">GoodFriday</holiday>
    <holiday id="4">EasterMonday</holiday>
    <holiday id="5">MayDay</holiday>
    <holiday id="6">SpringBank</holiday>
    <holiday id="7">LateSummerBankHolidayNotScotland</holiday>
    <holiday id="8">AugustBankHolidayScotland</holiday>
    <holiday id="9">ChristmasDay</holiday>
    <holiday id="10">BoxingDay</holiday>
    <holiday id="11">ChristmasDayHoliday</holiday>
    <holiday id="12">BoxingDayHoliday</holiday>
    <holiday id="13">NewYearsDayHoliday</holiday>
    <holiday id="14">ChristmasEve</holiday>
    <holiday id="15">NewYearsEve</holiday>
  </xsl:param>
  <xsl:param name="mode_ids">
    <mode id="1">bus</mode>
    <mode id="2">metro</mode>
    <mode id="3">tram</mode>
  </xsl:param>

  <xsl:key name="key_operators" match="txc:TransXChange/txc:Operators/txc:Operator" use="@id"/>
  <xsl:key name="key_routes" match="txc:TransXChange/txc:Routes/txc:Route" use="@id"/>
  <xsl:key name="key_route_links" match="txc:TransXChange/txc:RouteSections/txc:RouteSection/txc:RouteLink" use="@id"/>
  <xsl:key name="key_services" match="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]" use="txc:ServiceCode"/>
  <xsl:key name="key_patterns" match="txc:TransXChange/txc:Services/txc:Service/txc:StandardService/txc:JourneyPattern" use="@id"/>
  <xsl:key name="key_sections" match="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection" use="@id"/>
  <xsl:key name="key_journeys" match="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney" use="txc:VehicleJourneyCode"/>

  <xsl:template match="txc:TransXChange">
    <Data>
      <xsl:if test="boolean($services)">
        <xsl:apply-templates select="$operators" mode="national"/>
        <xsl:apply-templates select="$operators" mode="local"/>
        <xsl:apply-templates select="$services"/>
        <xsl:apply-templates select="$patterns"/>
        <xsl:apply-templates select="$patterns" mode="journey_links"/>
        <xsl:apply-templates select="$vehicle_journeys"/>
        <xsl:apply-templates select="$vehicle_journeys" mode="timing_links"/>
        <xsl:apply-templates select="$organisations"/>
        <xsl:apply-templates select="$organisations" mode="excluded_days"/>
        <xsl:apply-templates select="$organisations" mode="operating_periods"/>
        <xsl:apply-templates select="$vehicle_journeys" mode="organisations_served"/>
        <xsl:apply-templates select="$vehicle_journeys" mode="special_periods"/>
        <xsl:apply-templates select="$vehicle_journeys" mode="bank_holidays"/>
      </xsl:if>
    </Data>
  </xsl:template>

  <xsl:template match="txc:Operator" mode="national">
    <xsl:if test="func:national_op_new(txc:NationalOperatorCode)">
      <Operator>
        <code><xsl:value-of select="txc:NationalOperatorCode"/></code>
      </Operator>
    </xsl:if>
  </xsl:template>

  <xsl:template match="txc:Operator" mode="local">
    <xsl:if test="func:local_op_new(txc:OperatorCode, $region)">
      <LocalOperator>
        <operator_ref><xsl:value-of select="txc:NationalOperatorCode"/></operator_ref>
        <region_ref><xsl:value-of select="$region"/></region_ref>
        <code><xsl:value-of select="txc:OperatorCode"/></code>
        <name><xsl:value-of select="txc:OperatorShortName"/></name>
      </LocalOperator>
    </xsl:if>
  </xsl:template>

  <xsl:template match="txc:Service">
    <xsl:variable name="mode">
      <xsl:choose>
        <xsl:when test="boolean(txc:Mode = 'underground')">metro</xsl:when>
        <xsl:otherwise><xsl:value-of select="txc:Mode"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <Service>
      <code>
        <xsl:choose>
          <xsl:when test="starts-with(txc:PrivateCode, $region)"><xsl:value-of select="txc:PrivateCode"/></xsl:when>
          <xsl:when test="txc:PrivateCode"><xsl:value-of select="concat($region, '-', txc:PrivateCode)"/></xsl:when>
          <xsl:when test="starts-with(txc:ServiceCode, $region)"><xsl:value-of select="txc:ServiceCode"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat($region, '-', txc:ServiceCode)"/></xsl:otherwise>
        </xsl:choose>
      </code>
      <line><xsl:value-of select="func:l_split(txc:Lines/txc:Line[1]/txc:LineName, '|')"/></line>
      <description><xsl:value-of select="txc:Description"/></description>
      <local_operator_ref><xsl:value-of select="key('key_operators', txc:RegisteredOperatorRef)/txc:OperatorCode"/></local_operator_ref>
      <region_ref><xsl:value-of select="$region"/></region_ref>
      <mode><xsl:value-of select="exsl:node-set($mode_ids)/mode[.=$mode]/@id"/></mode>
    </Service>
  </xsl:template>

  <xsl:template match="txc:JourneyPattern">
    <xsl:variable name="direction">
      <xsl:choose>
        <xsl:when test="txc:Direction"><xsl:value-of select="txc:Direction"/></xsl:when>
        <xsl:when test="boolean(key('key_routes', txc:RouteRef)/txc:Direction)"><xsl:value-of
            select="key('key_routes', txc:RouteRef)/txc:Direction"/></xsl:when>
        <xsl:when test="ancestor::txc:Service/txc:Direction"><xsl:value-of select="ancestor::txc:Service/txc:Direction"/></xsl:when>
        <xsl:otherwise>outbound</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="service_direction">
      <xsl:choose>
        <xsl:when test="ancestor::txc:Service/txc:Direction[text()!='inboundAndOutbound']"><xsl:value-of select="ancestor::txc:Service/txc:Direction"/></xsl:when>
        <xsl:otherwise>outbound</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <JourneyPattern>
      <id><xsl:value-of select="func:add_id(@id, $file, 'JourneyPattern')"/></id>
      <xsl:choose>
        <xsl:when test="boolean($direction=$service_direction)">
          <origin><xsl:value-of select="ancestor::txc:Service/txc:StandardService/txc:Origin"/></origin>
          <destination><xsl:value-of select="ancestor::txc:Service/txc:StandardService/txc:Destination"/></destination>
        </xsl:when>
        <xsl:otherwise>
          <origin><xsl:value-of select="ancestor::txc:Service/txc:StandardService/txc:Destination"/></origin>
          <destination><xsl:value-of select="ancestor::txc:Service/txc:StandardService/txc:Origin"/></destination>
        </xsl:otherwise>
      </xsl:choose>
      <service_ref>
        <xsl:choose>
          <xsl:when test="starts-with(ancestor::txc:Service/txc:PrivateCode, $region)"><xsl:value-of select="ancestor::txc:Service/txc:PrivateCode"/></xsl:when>
          <xsl:when test="ancestor::txc:Service/txc:PrivateCode"><xsl:value-of select="concat($region, '-', ancestor::txc:Service/txc:PrivateCode)"/></xsl:when>
          <xsl:when test="starts-with(ancestor::txc:Service/txc:ServiceCode, $region)"><xsl:value-of select="ancestor::txc:Service/txc:ServiceCode"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat($region, '-', ancestor::txc:Service/txc:ServiceCode)"/></xsl:otherwise>
        </xsl:choose>
      </service_ref>
      <direction py_type="bool">
        <xsl:choose>
          <xsl:when test="boolean($direction=$service_direction)">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </direction>
      <date_start><xsl:value-of select="ancestor::txc:Service/txc:OperatingPeriod/txc:StartDate"/></date_start>
      <date_end><xsl:value-of select="ancestor::txc:Service/txc:OperatingPeriod/txc:EndDate"/></date_end>
    </JourneyPattern>
  </xsl:template>

  <xsl:template match="txc:JourneyPattern" mode="journey_links">
    <xsl:variable name="jp" select="."/>
    <xsl:for-each select="key('key_sections', txc:JourneyPatternSectionRefs)/txc:JourneyPatternTimingLink">
      <xsl:call-template name="journey_link">
        <xsl:with-param name="jp" select="$jp"/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="stop_timing">
    <xsl:param name="timing"/>
    <xsl:param name="start_end"/>
    <xsl:choose>
      <xsl:when test="boolean($timing='PTP')">
        <xsl:element name="timing_{$start_end}">1</xsl:element>
        <xsl:element name="principal_{$start_end}">1</xsl:element>
      </xsl:when>
      <xsl:when test="boolean($timing='PPT')">
        <xsl:element name="timing_{$start_end}">0</xsl:element>
        <xsl:element name="principal_{$start_end}">1</xsl:element>
      </xsl:when>
      <xsl:when test="boolean($timing='TIP')">
        <xsl:element name="timing_{$start_end}">1</xsl:element>
        <xsl:element name="principal_{$start_end}">0</xsl:element>
      </xsl:when>
      <xsl:when test="boolean($timing='OTH')">
        <xsl:element name="timing_{$start_end}">0</xsl:element>
        <xsl:element name="principal_{$start_end}">0</xsl:element>
      </xsl:when>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="journey_link">
    <xsl:param name="jp"/>
    <JourneyLink>
      <id><xsl:value-of select="func:add_id(concat($jp/@id, '-', @id), $file, 'JourneyLink')"/></id>
      <pattern_ref><xsl:value-of select="func:get_id($jp/@id, $file, 'JourneyPattern')"/></pattern_ref>
      <stop_start>
        <xsl:if test="func:stop_exists(txc:From/txc:StopPointRef)">
          <xsl:value-of select="txc:From/txc:StopPointRef"/>
        </xsl:if>
      </stop_start>
      <wait_start py_type="duration">
        <xsl:choose>
          <xsl:when test="txc:From/txc:WaitTime"><xsl:value-of select="txc:From/txc:WaitTime"/></xsl:when>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_start>
      <xsl:call-template name="stop_timing">
        <xsl:with-param name="timing"><xsl:value-of select="txc:From/txc:TimingStatus"/></xsl:with-param>
        <xsl:with-param name="start_end">start</xsl:with-param>
      </xsl:call-template>
      <stopping_start py_type="bool">
        <xsl:choose>
          <xsl:when test="txc:From[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping_start>
      <stop_end>
        <xsl:if test="func:stop_exists(txc:To/txc:StopPointRef)">
          <xsl:value-of select="txc:To/txc:StopPointRef"/>
        </xsl:if>
      </stop_end>
      <wait_end py_type="duration">
        <xsl:choose>
          <xsl:when test="txc:To/txc:WaitTime"><xsl:value-of select="txc:To/txc:WaitTime"/></xsl:when>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_end>
      <xsl:call-template name="stop_timing">
        <xsl:with-param name="timing"><xsl:value-of select="txc:To/txc:TimingStatus"/></xsl:with-param>
        <xsl:with-param name="start_end">end</xsl:with-param>
      </xsl:call-template>
      <stopping_end py_type="bool">
        <xsl:choose>
          <xsl:when test="txc:To[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping_end>
      <run_time py_type="duration"><xsl:value-of select="txc:RunTime"/></run_time>
      <sequence><xsl:value-of select="position()"/></sequence>
    </JourneyLink>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney">
    <xsl:variable name="jp_id">
      <xsl:choose>
        <xsl:when test="txc:JourneyPatternRef"><xsl:value-of select="txc:JourneyPatternRef"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_op" select="key('key_journeys', txc:VehicleJourneyRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_jp_op" select="key('key_patterns', key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <Journey>
      <id><xsl:value-of select="func:add_id(txc:VehicleJourneyCode, $file, 'Journey')"/></id>
      <service_ref>
        <xsl:choose>
          <xsl:when test="starts-with(key('key_services', txc:ServiceRef)/txc:PrivateCode, $region)"><xsl:value-of select="key('key_services', txc:ServiceRef)/txc:PrivateCode"/></xsl:when>
          <xsl:when test="key('key_services', txc:ServiceRef)/txc:PrivateCode"><xsl:value-of select="concat($region, '-', key('key_services', txc:ServiceRef)/txc:PrivateCode)"/></xsl:when>
          <xsl:when test="starts-with(txc:ServiceRef, $region)"><xsl:value-of select="txc:ServiceRef"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="concat($region, '-', txc:ServiceRef)"/></xsl:otherwise>
        </xsl:choose>
      </service_ref>
      <pattern_ref><xsl:value-of select="func:get_id($jp_id, $file, 'JourneyPattern')"/></pattern_ref>
      <start_run>
        <xsl:if test="txc:StartDeadRun/txc:ShortWorking">
          <xsl:value-of select="func:get_id(concat($jp_id, '-', txc:StartDeadRun/txc:ShortWorking/txc:JourneyPatternTimingLinkRef), $file, 'JourneyLink')"/>
        </xsl:if>
      </start_run>
      <end_run>
        <xsl:if test="txc:EndDeadRun/txc:ShortWorking">
          <xsl:value-of select="func:get_id(concat($jp_id, '-', txc:EndDeadRun/txc:ShortWorking/txc:JourneyPatternTimingLinkRef), $file, 'JourneyLink')"/>
        </xsl:if>
      </end_run>
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
        <xsl:when test="$vj_op">
          <days><xsl:value-of select="func:days_week($vj_op/txc:RegularDayType)"/></days>
          <weeks><xsl:value-of select="func:weeks_month($vj_op/txc:PeriodicDayType)"/></weeks>
        </xsl:when>
        <xsl:when test="$vj_jp_op">
          <days><xsl:value-of select="func:days_week($vj_jp_op/txc:RegularDayType)"/></days>
          <weeks><xsl:value-of select="func:weeks_month($vj_jp_op/txc:PeriodicDayType)"/></weeks>
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

  <xsl:template name="journey_specific_link">
    <xsl:param name="vj_code"/>
    <xsl:param name="jp_id"/>
    <JourneySpecificLink>
      <link_ref><xsl:value-of select="func:get_id(concat($jp_id, '-', txc:JourneyPatternTimingLinkRef), $file, 'JourneyLink')"/></link_ref>
      <journey_ref><xsl:value-of select="func:get_id($vj_code, $file, 'Journey')"/></journey_ref>
      <wait_start py_type="duration"><xsl:value-of select="txc:From/txc:WaitTime"/></wait_start>
      <stopping_start py_type="bool">
        <xsl:if test="txc:From/txc:Activity">
          <xsl:choose>
            <xsl:when test="txc:From[txc:Activity[.='pass']]">0</xsl:when>
            <xsl:otherwise>1</xsl:otherwise>
          </xsl:choose>
        </xsl:if>
      </stopping_start>
      <wait_end py_type="duration"><xsl:value-of select="txc:To/txc:WaitTime"/></wait_end>
      <stopping_end py_type="bool">
        <xsl:if test="txc:To/txc:Activity">
          <xsl:choose>
            <xsl:when test="txc:To[txc:Activity[.='pass']]">0</xsl:when>
            <xsl:otherwise>1</xsl:otherwise>
          </xsl:choose>
        </xsl:if>
      </stopping_end>
      <run_time py_type="duration"><xsl:value-of select="txc:RunTime"/></run_time>
    </JourneySpecificLink>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="timing_links">
    <xsl:variable name="vj_code" select="txc:VehicleJourneyCode"/>
    <xsl:choose>
      <xsl:when test="txc:VehicleJourneyTimingLink">
        <xsl:variable name="jp_id" select="txc:JourneyPatternRef"/>
        <xsl:for-each select="txc:VehicleJourneyTimingLink">
          <xsl:call-template name="journey_specific_link">
            <xsl:with-param name="vj_code" select="$vj_code"/>
            <xsl:with-param name="jp_id" select="$jp_id"/>
          </xsl:call-template>
        </xsl:for-each>
      </xsl:when>
      <xsl:when test="key('key_journeys', txc:VehicleJourneyRef)/txc:VehicleJourneyTimingLink">
        <xsl:variable name="jp_id" select="key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef"/>
        <xsl:for-each select="key('key_journeys', txc:VehicleJourneyRef)/txc:VehicleJourneyTimingLink">
          <xsl:call-template name="journey_specific_link">
            <xsl:with-param name="vj_code" select="$vj_code"/>
            <xsl:with-param name="jp_id" select="$jp_id"/>
          </xsl:call-template>
        </xsl:for-each>
      </xsl:when>
    </xsl:choose>
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

  <xsl:template match="txc:ServicedOrganisation" mode="operating_periods">
    <xsl:for-each select=".//txc:DateRange">
      <OperatingPeriod>
        <org_ref><xsl:value-of select="concat($region, ancestor::txc:ServicedOrganisation/txc:OrganisationCode)"/></org_ref>
        <date_start><xsl:value-of select="txc:StartDate"/></date_start>
        <date_end>
          <xsl:choose>
            <xsl:when test="boolean(txc:EndDate)"><xsl:value-of select="txc:EndDate"/></xsl:when>
            <xsl:otherwise><xsl:value-of select="txc:StartDate"/></xsl:otherwise>
          </xsl:choose>
        </date_end>
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
      <journey_ref><xsl:value-of select="func:get_id(ancestor::txc:VehicleJourney/txc:VehicleJourneyCode, $file, 'Journey')"/></journey_ref>
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
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_op" select="key('key_journeys', txc:VehicleJourneyRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_jp_op" select="key('key_patterns', key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$jp_op">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="$jp_op/txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_op">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="$vj_op/txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_jp_op">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="$vj_jp_op/txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$s_op">
        <xsl:call-template name="sequence_organisation_days">
          <xsl:with-param name="refs" select="$s_op/txc:OperatingProfile//txc:ServicedOrganisationRef"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="special_days">
    <xsl:param name="id"/>
    <SpecialPeriod>
      <journey_ref><xsl:value-of select="$id"/></journey_ref>
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
    <xsl:param name="id"/>
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="special_days">
        <xsl:with-param name="id" select="$id"/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="special_periods">
    <xsl:variable name="id" select="func:get_id(txc:VehicleJourneyCode, $file, 'Journey')"/>
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_op" select="key('key_journeys', txc:VehicleJourneyRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_jp_op" select="key('key_patterns', key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="txc:OperatingProfile//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$jp_op">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$jp_op//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_op">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$vj_op//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_jp_op">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$vj_jp_op//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$s_op">
        <xsl:call-template name="sequence_special">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$s_op//txc:DateRange"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="bank_holiday_group">
    <xsl:param name="id">0</xsl:param>
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
          <holiday><xsl:value-of select="$holiday"/></holiday>
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
      <xsl:variable name="name" select="text()"/>
      <BankHolidays>
        <holiday_ref><xsl:value-of select="exsl:node-set($bank_holiday_ids)/holiday[.=$name]/@id"/></holiday_ref>
        <journey_ref><xsl:value-of select="$id"/></journey_ref>
        <operational py_type="bool"><xsl:value-of select="$operational"/></operational>
      </BankHolidays>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="sequence_bank_holidays">
    <xsl:param name="id"/>
    <xsl:param name="refs"/>
    <xsl:for-each select="$refs">
      <xsl:call-template name="bank_holiday_group">
        <xsl:with-param name="id" select="$id"/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="bank_holidays">
    <xsl:variable name="id" select="func:get_id(txc:VehicleJourneyCode, $file, 'Journey')"/>
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_op" select="key('key_journeys', txc:VehicleJourneyRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_jp_op" select="key('key_patterns', key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="txc:OperatingProfile/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$jp_op">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$jp_op/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_op">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$vj_op/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_jp_op">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$vj_jp_op/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$s_op">
        <xsl:call-template name="sequence_bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$s_op/txc:BankHolidayOperation/*/*"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>
</xsl:transform>