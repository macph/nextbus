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
    [txc:Mode[.='underground' or .='metro' or .='bus' or .='coach' or .='tram']]"/>
  <xsl:param name="patterns" select="$services/txc:StandardService/txc:JourneyPattern"/>
  <xsl:param name="journey_links" select="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection/txc:JourneyPatternTimingLink"/>

  <xsl:param name="organisations" select="txc:TransXChange/txc:ServicedOrganisations/txc:ServicedOrganisation"/>

  <xsl:param name="vehicle_journeys" select="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney"/>

  <xsl:param name="mode_ids">
    <mode id="1">bus</mode>
    <mode id="2">coach</mode>
    <mode id="3">tram</mode>
    <mode id="4">metro</mode>
    <mode id="5">underground</mode>
  </xsl:param>
  <xsl:param name="set_mode_ids" select="exsl:node-set($mode_ids)"/>

  <xsl:key name="key_operators" match="txc:TransXChange/txc:Operators/txc:Operator" use="@id"/>
  <xsl:key name="key_routes" match="txc:TransXChange/txc:Routes/txc:Route" use="@id"/>
  <xsl:key name="key_route_links" match="txc:TransXChange/txc:RouteSections/txc:RouteSection/txc:RouteLink" use="@id"/>
  <xsl:key name="key_services" match="txc:TransXChange/txc:Services/txc:Service[txc:StandardService]" use="txc:ServiceCode"/>
  <xsl:key name="key_patterns" match="txc:TransXChange/txc:Services/txc:Service/txc:StandardService/txc:JourneyPattern" use="@id"/>
  <xsl:key name="key_sections" match="txc:TransXChange/txc:JourneyPatternSections/txc:JourneyPatternSection" use="@id"/>
  <xsl:key name="key_journeys" match="txc:TransXChange/txc:VehicleJourneys/txc:VehicleJourney" use="txc:VehicleJourneyCode"/>

  <xsl:template match="txc:TransXChange">
    <Data>
      <xsl:if test="not(@Modification='Delete' or @Modification='delete') and boolean($services)">
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
    <xsl:variable name="mode" select="$services/txc:Mode"/>
    <xsl:if test="txc:NationalOperatorCode and txc:OperatorShortName != ''">
      <Operator>
        <code><xsl:value-of select="txc:NationalOperatorCode"/></code>
        <region_ref><xsl:value-of select="$region"/></region_ref>
        <name><xsl:value-of select="txc:OperatorShortName"/></name>
        <mode><xsl:value-of select="$set_mode_ids/mode[.=$mode]/@id"/></mode>
      </Operator>
    </xsl:if>
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
    <xsl:variable name="mode" select="txc:Mode"/>
    <Service>
      <id><xsl:value-of select="func:add_id('Service', $file)"/></id>
      <code>
        <xsl:choose>
          <xsl:when test="txc:PrivateCode"><xsl:value-of select="txc:PrivateCode"/></xsl:when>
          <xsl:otherwise><xsl:value-of select="txc:ServiceCode"/></xsl:otherwise>
        </xsl:choose>
      </code>
      <line><xsl:value-of select="func:l_split(txc:Lines/txc:Line[1]/txc:LineName, '|')"/></line>
      <description default="">
        <xsl:if test="txc:Description">
          <xsl:value-of select="func:format_description(txc:Description)"/>
        </xsl:if>
      </description>
      <mode><xsl:value-of select="$set_mode_ids/mode[.=$mode]/@id"/></mode>
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
      <id><xsl:value-of select="func:add_id('JourneyPattern', $file, @id)"/></id>
      <xsl:choose>
        <xsl:when test="boolean($direction=$service_direction)">
          <origin><xsl:value-of select="func:format_destination(ancestor::txc:Service/txc:StandardService/txc:Origin)"/></origin>
          <destination><xsl:value-of select="func:format_destination(ancestor::txc:Service/txc:StandardService/txc:Destination)"/></destination>
        </xsl:when>
        <xsl:otherwise>
          <origin><xsl:value-of select="func:format_destination(ancestor::txc:Service/txc:StandardService/txc:Destination)"/></origin>
          <destination><xsl:value-of select="func:format_destination(ancestor::txc:Service/txc:StandardService/txc:Origin)"/></destination>
        </xsl:otherwise>
      </xsl:choose>
      <service_ref><xsl:value-of select="func:get_id('Service', $file)"/></service_ref>
      <local_operator_ref><xsl:value-of select="key('key_operators', ancestor::txc:Service/txc:RegisteredOperatorRef)/txc:OperatorCode"/></local_operator_ref>
      <region_ref><xsl:value-of select="$region"/></region_ref>
      <direction>
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
    <xsl:variable name="links">
      <xsl:for-each select="txc:JourneyPatternSectionRefs">
        <xsl:copy-of select="key('key_sections', .)/txc:JourneyPatternTimingLink"/>
      </xsl:for-each>
    </xsl:variable>
    <xsl:apply-templates select="exsl:node-set($links)/txc:JourneyPatternTimingLink[1]" mode="start">
      <xsl:with-param name="jp" select="$jp"/>
    </xsl:apply-templates>
    <xsl:apply-templates select="exsl:node-set($links)" mode="end">
      <xsl:with-param name="jp" select="$jp"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template name="stop_timing">
    <xsl:param name="timing"/>
    <xsl:choose>
      <xsl:when test="boolean($timing='PTP')">
        <timing_point>1</timing_point>
        <principal_point>1</principal_point>
      </xsl:when>
      <xsl:when test="boolean($timing='PPT')">
        <timing_point>0</timing_point>
        <principal_point>1</principal_point>
      </xsl:when>
      <xsl:when test="boolean($timing='TIP')">
        <timing_point>1</timing_point>
        <principal_point>0</principal_point>
      </xsl:when>
      <xsl:when test="boolean($timing='OTH')">
        <timing_point>0</timing_point>
        <principal_point>0</principal_point>
      </xsl:when>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternTimingLink" mode="start">
    <xsl:param name="jp"/>
    <JourneyLink>
      <id><xsl:value-of select="func:add_id('JourneyLink', $file, $jp/@id, @id, 's')"/></id>
      <pattern_ref><xsl:value-of select="func:get_id('JourneyPattern', $file, $jp/@id)"/></pattern_ref>
      <stop_point_ref>
        <xsl:if test="func:stop_exists($file, txc:From/txc:StopPointRef)">
          <xsl:value-of select="txc:From/txc:StopPointRef"/>
        </xsl:if>
      </stop_point_ref>
      <run_time/>
      <wait_arrive/>
      <wait_leave>
        <xsl:choose>
          <xsl:when test="txc:From/txc:WaitTime"><xsl:value-of select="txc:From/txc:WaitTime"/></xsl:when>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_leave>
      <xsl:call-template name="stop_timing">
        <xsl:with-param name="timing"><xsl:value-of select="txc:From/txc:TimingStatus"/></xsl:with-param>
      </xsl:call-template>
      <stopping>
        <xsl:choose>
          <xsl:when test="txc:From[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping>
      <sequence><xsl:value-of select="1"/></sequence>
    </JourneyLink>
  </xsl:template>

  <xsl:template match="txc:JourneyPatternTimingLink" mode="end">
    <xsl:param name="jp"/>
    <xsl:variable name="next_jl" select="following-sibling::txc:JourneyPatternTimingLink[1]"/>
    <JourneyLink>
      <id><xsl:value-of select="func:add_id('JourneyLink', $file, $jp/@id, @id, 'e')"/></id>
      <pattern_ref><xsl:value-of select="func:get_id('JourneyPattern', $file, $jp/@id)"/></pattern_ref>
      <stop_point_ref>
        <xsl:if test="func:stop_exists($file, txc:To/txc:StopPointRef)">
          <xsl:value-of select="txc:To/txc:StopPointRef"/>
        </xsl:if>
      </stop_point_ref>
      <run_time><xsl:value-of select="txc:RunTime"/></run_time>
      <wait_arrive>
        <xsl:choose>
          <xsl:when test="txc:To/txc:WaitTime"><xsl:value-of select="txc:To/txc:WaitTime"/></xsl:when>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_arrive>
      <wait_leave>
        <xsl:choose>
          <xsl:when test="$next_jl/txc:From/txc:WaitTime"><xsl:value-of select="$next_jl/txc:From/txc:WaitTime"/></xsl:when>
          <xsl:when test="position() = last()"/>
          <xsl:otherwise>PT0S</xsl:otherwise>
        </xsl:choose>
      </wait_leave>
      <xsl:call-template name="stop_timing">
        <xsl:with-param name="timing"><xsl:value-of select="txc:To/txc:TimingStatus"/></xsl:with-param>
      </xsl:call-template>
      <stopping>
        <xsl:choose>
          <xsl:when test="txc:To[txc:Activity[.='pass']]">0</xsl:when>
          <xsl:otherwise>1</xsl:otherwise>
        </xsl:choose>
      </stopping>
      <sequence><xsl:value-of select="count(preceding-sibling::txc:JourneyPatternTimingLink) + 2"/></sequence>
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
      <id><xsl:value-of select="func:add_id('Journey', $file, txc:VehicleJourneyCode)"/></id>
      <pattern_ref><xsl:value-of select="func:get_id('JourneyPattern', $file, $jp_id)"/></pattern_ref>
      <start_run>
        <xsl:if test="txc:StartDeadRun/txc:ShortWorking">
          <xsl:value-of select="func:get_id('JourneyLink', $file, $jp_id, txc:StartDeadRun/txc:ShortWorking/txc:JourneyPatternTimingLinkRef, 'e')"/>
        </xsl:if>
      </start_run>
      <end_run>
        <xsl:if test="txc:EndDeadRun/txc:ShortWorking">
          <xsl:value-of select="func:get_id('JourneyLink', $file, $jp_id, txc:EndDeadRun/txc:ShortWorking/txc:JourneyPatternTimingLinkRef, 'e')"/>
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
      <note_code><xsl:value-of select="txc:Note/txc:NoteCode"/></note_code>
      <note_text><xsl:value-of select="txc:Note/txc:NoteText"/></note_text>
    </Journey>
  </xsl:template>

  <xsl:template name="journey_specific_link">
    <xsl:param name="vj_code"/>
    <xsl:param name="jp_id"/>
    <xsl:variable name="jl" select="key('key_links', txc:JourneyPatternTimingLinkRef)"/>
    <xsl:variable name="vhjl_before" select="preceding-sibling::txc:VehicleJourneyTimingLink[1]"/>
    <JourneySpecificLink>
      <id><xsl:value-of select="func:add_id('JourneySpecificLink')"/></id>
      <link_ref><xsl:value-of select="func:get_id('JourneyLink', $file, $jp_id, txc:JourneyPatternTimingLinkRef, 'e')"/></link_ref>
      <journey_ref><xsl:value-of select="func:get_id('Journey', $file, $vj_code)"/></journey_ref>
      <run_time><xsl:value-of select="txc:RunTime"/></run_time>
      <wait_arrive><xsl:value-of select="preceding-sibling::txc:VehicleJourneyTimingLink[1]/txc:To/txc:WaitTime"/></wait_arrive>
      <wait_leave><xsl:value-of select="txc:From/txc:WaitTime"/></wait_leave>
      <stopping>
        <xsl:if test="txc:From/txc:Activity">
          <xsl:choose>
            <xsl:when test="txc:From[txc:Activity[.='pass']]">0</xsl:when>
            <xsl:otherwise>1</xsl:otherwise>
          </xsl:choose>
        </xsl:if>
      </stopping>
    </JourneySpecificLink>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="timing_links">
    <xsl:variable name="vj_code" select="txc:VehicleJourneyCode"/>
    <xsl:choose>
      <xsl:when test="txc:VehicleJourneyTimingLink">
        <xsl:variable name="jp_id" select="txc:JourneyPatternRef"/>
        <xsl:for-each select="txc:VehicleJourneyTimingLink[position() > 1]">
          <xsl:call-template name="journey_specific_link">
            <xsl:with-param name="vj_code" select="$vj_code"/>
            <xsl:with-param name="jp_id" select="$jp_id"/>
          </xsl:call-template>
        </xsl:for-each>
      </xsl:when>
      <xsl:when test="key('key_journeys', txc:VehicleJourneyRef)/txc:VehicleJourneyTimingLink">
        <xsl:variable name="jp_id" select="key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef"/>
        <xsl:for-each select="key('key_journeys', txc:VehicleJourneyRef)/txc:VehicleJourneyTimingLink[position() > 1]">
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
    <xsl:variable name="code" select="txc:OrganisationCode"/>
    <xsl:for-each select="//txc:DateExclusion">
      <ExcludedDate>
        <id><xsl:value-of select="func:add_id('ExcludedDate')"/></id>
        <org_ref><xsl:value-of select="concat($region, $code)"/></org_ref>
        <date><xsl:value-of select="current()"/></date>
        <working>
          <xsl:choose>
            <xsl:when test="ancestor::txc:WorkingDays">1</xsl:when>
            <xsl:otherwise>0</xsl:otherwise>
          </xsl:choose>
        </working>
      </ExcludedDate>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="txc:ServicedOrganisation" mode="operating_periods">
    <xsl:variable name="code" select="txc:OrganisationCode"/>
    <xsl:for-each select=".//txc:DateRange">
      <OperatingPeriod>
        <id><xsl:value-of select="func:add_id('OperatingPeriod')"/></id>
        <org_ref><xsl:value-of select="concat($region, $code)"/></org_ref>
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
      <journey_ref><xsl:value-of select="func:get_id('Journey', $file, ancestor::txc:VehicleJourney/txc:VehicleJourneyCode)"/></journey_ref>
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
      <id><xsl:value-of select="func:add_id('SpecialPeriod')"/></id>
      <journey_ref><xsl:value-of select="$id"/></journey_ref>
      <date_start><xsl:value-of select="txc:StartDate"/></date_start>
      <date_end><xsl:value-of select="txc:EndDate"/></date_end>
      <operational>
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
    <xsl:variable name="id" select="func:get_id('Journey', $file, txc:VehicleJourneyCode)"/>
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

  <xsl:template name="bank_holidays">
    <xsl:param name="id"/>
    <xsl:param name="refs"/>
    <xsl:if test="$refs/txc:DaysOfOperation">
      <BankHolidays>
        <holidays><xsl:value-of select="func:bank_holidays($refs/txc:DaysOfOperation, $region)"/></holidays>
        <journey_ref><xsl:value-of select="$id"/></journey_ref>
        <operational>1</operational>
      </BankHolidays>
    </xsl:if>
    <xsl:if test="$refs/txc:DaysOfNonOperation">
      <BankHolidays>
        <holidays><xsl:value-of select="func:bank_holidays($refs/txc:DaysOfNonOperation, $region)"/></holidays>
        <journey_ref><xsl:value-of select="$id"/></journey_ref>
        <operational>0</operational>
      </BankHolidays>
    </xsl:if>
  </xsl:template>

  <xsl:template match="txc:VehicleJourney" mode="bank_holidays">
    <xsl:variable name="id" select="func:get_id('Journey', $file, txc:VehicleJourneyCode)"/>
    <xsl:variable name="jp_op" select="key('key_patterns', txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_op" select="key('key_journeys', txc:VehicleJourneyRef)/txc:OperatingProfile"/>
    <xsl:variable name="vj_jp_op" select="key('key_patterns', key('key_journeys', txc:VehicleJourneyRef)/txc:JourneyPatternRef)/txc:OperatingProfile"/>
    <xsl:variable name="s_op" select="key('key_services', txc:ServiceRef)/txc:OperatingProfile"/>
    <xsl:choose>
      <xsl:when test="txc:OperatingProfile">
        <xsl:call-template name="bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="txc:OperatingProfile/txc:BankHolidayOperation"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$jp_op">
        <xsl:call-template name="bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$jp_op/txc:BankHolidayOperation"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_op">
        <xsl:call-template name="bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$vj_op/txc:BankHolidayOperation"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$vj_jp_op">
        <xsl:call-template name="bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$vj_jp_op/txc:BankHolidayOperation"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="$s_op">
        <xsl:call-template name="bank_holidays">
          <xsl:with-param name="id" select="$id"/>
          <xsl:with-param name="refs" select="$s_op/txc:BankHolidayOperation"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>
  </xsl:template>
</xsl:transform>