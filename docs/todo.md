# To do...

## Set up the website

- ~~Find out more about SQLite or PostgresSQL and convert NaPTAN data over to a SQL database for use by the website.~~
- ~~Implement the NaPTAN and NPTG data in a SQLite database. Set up a script for doing this work.~~
- ~~Integrate NSPL data with NPTG, if that's possible.~~
- ~~Set up the website.~~

Set up the routing as such:

- `/` & `/home` **Home page**: search for bus stop, route, etc
    - `/list` **List of regions**: List of all regions.
        - `/list/region/<code>` **List of areas/districts**: List of areas and districts in a region
            - `/list/area/<code>` **List of localities**: List of localities in an area
            - `/list/district/<code>` **List of localities**: List of localities in an district
    - `/near` Placeholder
        - `/near/locality/<code>` **List of stops**: List of stops in a locality
        - `/near/postcode/<psc>` **List of stops**: List of stops around a postcode
        - `/near/location/<lat,long>` **List of stops**: List of stops around a GPS coordinate
    - `/stop` Placeholder
        - `/stop/naptan/<code>` **Stop info**: Stop with NaPTAN code
        - `/stop/atco/<code>` **Stop info**: Stop with ATCO code
        - `/stop/area/<code>` **Stop info for area**: Stops in stop area with stop area code
    - `/search/<string>` **Search**: Find an area, district, locality or stop name

### ~~Changes to area list~~

Do we move to a setup where we have a list of regions only, maybe with map, and each region has list of areas and districts combined - for example Yorkshire would have a list of all districts _and_ the areas which do not have any districts (marked with *):

- Barnsley
- Bradford
- Calderdale
- Craven
- East Riding of Yorkshire *
- Doncaster
- Hambleton
- Harrogate
- Kingston upon Hull *
- Kirklees
- Leeds
- Richmondshire
- Rotherham
- Ryedale
- Scarborough
- Selby
- Sheffield
- Wakefield
- York *

In this case:

- `/list` **List of regions**: List of all regions.
    - `/list/region/<code>` **List of areas/districts**: List of areas and districts in a region
        - `/list/area/<code>` **List of localities**: List of localities in an area
        - `/list/district/<code>` **List of localities**: List of localities in an district

## Migrate to PostgreSQL

Consider switching over to a PostgreSQL DB for compatibility with cloud providers and FT search.
- Install the `psycopg2` module to let SQLAlchemy interact with the PSQL server.
- Use extra features provided by PostgreSQL, such as `ON CONFLICT`:

```sql
INSERT INTO stop_point AS sp (atco_code, naptan_code, modified ...)
     VALUES ('490008978N1', '75463', '2017-11-21 16:53:00' ...)
ON CONFLICT (atco_code) /* or 'ON CONSTRAINT constraint' instead of '(sp.atco_code)'. */
            DO UPDATE SET atco_code='490008978N1',
                          naptan_code='75463',
                          modified='2017-11-21 16:53:00',
                          ...
      WHERE sp.modified < '2017-11-21 16:53:00'; /* must prefix with table name */
```

- Consider getting 2 databases - static for all data such as postcodes and stops, and users/dynamic for users, eg tracking and cookies.
- Settings per user (eg with cookies) - may want to start tracking once they
set up favourites or such?
- Consider changing DB tables such that:
    - Harmonise names (mix of short and common names) - makes it easier to sort.
        - Do this by accepting `CommonName` as the default, else use `ShortName`. Single `name` column in table.
    - ~~Short version of indicator for labelling.~~
    - ~~Remove all unnecessary data fields, eg town/suburb as they are already covered by locality.~~
    - ~~Add fields for colour - background and text/logo. See table.~~ *ATCO code/admin area code no longer necessary as the same code is used as the first 3 digits of stop's ATCO code.
    - ~~Live tracking enabled areas - a whitelist (London, SY, GM, etc would qualify)~~
    - Change locality name to place - or at least, do this for front facing pages.
    - ~~Add an surrogate primary key to stop points and stop areas; this should help with LEFT JOINs for localities (detecting whether a locality has any stops or not).~~ *Was done simply by indexing the locality code and the names (for ordering.)*
    - Index the correct columns.
        - ~~Add `tsvector` GIN indexes to all area and stop names (including streets) for full text searches.~~
        - Consider using GIN index on NaPTAN codes to speed up searches using `pg_trgm`. The alternative is to capitalize all codes and use a `LIKE` query which already uses indices.
    - ~~Capitalize *all* ATCO and NaPTAN codes. This speeds up searches significantly.~~
- ~~Find out why the query to match stop areas with localities was hanging up~~ *Fixed with autocommit enabled for SQLAlchemy.*
- ~~Add GIN indices for text search; because the `to_tsvector` function is used, migrations involving functional indices cannot add them automatically. We add something like these to the migration script:~~

```sql
CREATE INDEX ix_region_tsvector_name
          ON region
       USING gin (to_tsvector('english'), "name");
```

```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    # sa.text() reads string and injects into SQL query directly
    op.create_index('ix_region_tsvector_name', 'region',
                    [sa.text("to_tsvector('english', name)")],
                    unique=False, postgresql_using='gin')

def downgrade():
    op.drop_index('ix_region_tsvector_name', table_name='region')

```
- With PSQL implemented, add proper search fields
    - Correct ATCO/NaPTAN/SMS codes should send you to the correct stop/stop area page straightaway
    - Text search covering areas, localities, stops (common name & street) and stop area names.
    - With FTS, add options to filter by area or type.

```sql
SELECT atco_code, common_name, indicator
  FROM stop_point
 WHERE to_tsvector('english', common_name || ' ' || street)
       @@
       to_tsquery('english' 'crook');
```

```python
from nextbus import db, models

stops = (db.session.query(models.StopPoint.atco_code,
                          models.StopPoint.common_name,
                          models.StopPoint.indicator)
         .filter(db.func.to_tsvector('english', models.StopPoint.common_name
                                     + ' ' + models.StopPoint.street)
                 .match('crook', postgresql_regconfig='english'))
        ).all()
```

- **Need to format strings for use by `tsquery` , for example `ringstead crescent` needs to be parsed as `ringstead & crescent`.**
    - Search rules:
        - Words separated by spaces or `+` will be evaluated together.
        - Words separated by `or` or `|` will be evaluated separately.
        - Words prefixed by `-` or `!` will be excluded by the search.
        - Words enclosed within brackets `()` are evaluated before rest of the query.
    - With `tsquery` we have the operators `&`, `|`, `!`, `()` and `''' '''`:
        - `fat & cat` -> `fat AND cat`
        - `fat | cat` -> `fat OR cat`
        - `fat & ! cat` -> `fat AND NOT cat`
        - `fat & (cat | rat)` -> `fat AND (cat OR rat)`
    - So a parsing algorithm goes like this:
        - Replace `+` with a space.
        - Check if brackets do work -- use function recursively. Raise `ValueError` if required
        - Split up all by spaces -- can use `str.split()` or `re.split(r'\W', ...)`
        - In list: replace `or` (any case) with `|`, and split words starting with `|`
        - Strip any items or words without alphanumeric characters, except if they are prefixed with `-` or `!` (replace with `!`).
- **Need to use `coalesce` for indicators (and maybe names?), to parse `NULL` entries as `''`.**
- Add functionality to populate functions to remove districts without any associated localities, or at least change the district queries to exclude these districts.


## Styling website

- Create a webfont with icons: bus/tram, TfL roundel, arrows, search, refresh, etc. This would allow the bus/tram icons to be of different colours without having to use JS to modify the SVG colours.
- ~~Refine templates further such that the list of stops for localities, postcodes and locations all come from the same template, with a list of stop points as an object. Same goes for live times for ATCO and NaPTAN codes.~~
- Add info panel for more details about stop; by default only show street & SMS code
- Add maps for easier navigation.
    - Only load when required (eg 'Show location' button) - limits requests & reduce load on phones
    - For stops do a simple embed. (Embed API)
    - With streetview, set it up so that it points in right direction. (Embed API?)
    - For places, stop areas, postcodes and GPS: show stops with indicators. (JS API)
    - Use Google Maps' APIs, or use an openly available solution? May need to self-host.
    - **On Firefox, the stop page's map cannot be loaded - it seems to be activated already?**
    - **Consider whether to use OpenStreetMap with leaflet.js or continue with Google Maps.**
- Set up stop area page such that
    - Info about area
    - Map with all stops
    - Section for each stop in area with live bus times
    - Style:
        - Border between each stop
        - When expanded, have vertical border & bottom border, with margin at bottom and white background. All content goes here.
        - Only one section at a time. Close others when selecting a new stop.
        - For paired stops should we have a single table??
        - Request time, SMS code, link to single stop, table of services.
        - Get a link from map to stop in question with JS, makes it easier to navigate.
        - Anchor tags to open a stop automatically?
- ~~Index stops in locality if there are too many?~~
- ~~Change JS for live data to allow pausing of interval or stopping it, so can wait for the response to come back, or stop when focus is switched to another stop in area.~~
- ~~Fix height of services; add another div within with height fixed by content not the grid~~
- Take a look at how different pages call the SQL database; if only calling a specific column value it would be a waste to get the object for that row and then retrieve the attribute in question. If calling a number of attributes, can do a single query and output to a dict in the view function to be passed to the template page. So, instead of doing `stop_point.locality.name`, do

```python
db.session.query(models.Locality.name).filter_by(
    code=stop_point.locality_code
).scalar()
```

### ~~Admin area colours~~
| ATCO code | Area code | Area name  | Stop colour   | Text colour   |
| --------- | --------- | ---------- | ------------- | ------------- |
| 180       | 083       | Manchester | Dark grey     |               |
| 259       | 003       | Blackpool  | Grey          | Bright yellow |
| 280       | 090       | Merseyside | Bright yellow | Grey          |
| 339       | 039       | Nottingham | Turquoise     |               |
| 450       | 107       | West Yorks | Blue          |               |
| 490       | 082       | London     | TfL red       |               |
| 571       | 011       | Cardiff    | Dark green    |               |
| 609       | 127       | Glasgow    | Orange        |               |
| 620       | 124       | Edinburgh  | Maroon        |               |

How would the colours be encoded?

- One column for a text value for class name, so for TfL red:

```css
/* Transport for London */
div.area-color-490 {
    background: rgb(220, 36, 31);
}
```

- Add search to homepage and header.
- Set up the search results to have no columns, and:
    - Each locality should have area and/or district names as well.
    - Each stop point/area should have locality and street as well.
    - These supplementary info should be linkable in some way.
    - Stop areas should have their own logos - what to use?

## Responses for requests

- Sort out response handling for:
    - `stop_get_times()` POST response; need to pass on any errors from retrieving data to the JS
    - `LiveData` JS object; need to handle errors (eg 400, 404, 500) gracefully and let the user know.
    - `get_nextbus_times()` function for accessing API; need to pass on the right errors.
- Change JS to report on live data status (timed out, server unavailable, can't reach API, etc)
    - When POST request is sent, change heading to 'Updating live data' or 'Retrieving live data'.
    - Change back to 'Live times at HH:MM:SS' when data is retrieved and parsed.
- If no response is received:
    - Display message (timed out, unavailable, etc)
    - ~~Change the time remaining by cutting off a minute off and any live times could be changed to timetabled alternative, or simulated with red text to indicate they are not tracked at present. This requires including _both_ live and timetabled times - use ISO formats and let JS do the minute calculations?~~

## What else?

- ~~Set up TransportAPI querying, convert to data to be used by the website. Make a distinction between live and timetabled times.~~
- ~~Should we set up the URLs such that we have `/stop?naptan=51201` or `/list?postcode=W1A 1AA`, instead of `/naptan/51201` or `/postcode/W1A 1AA`?~~
- ~~How to retrieve lat/long data? Set up a JS function, and have it operate upon pressing a button.~~
- ~~Check why the lat/long->OS grid calculations are off; try direct geodesic calculations instead?~~
- ~~How to handle stop points without NaPTAN codes? Best solution would be to drop all entries with no NaPTAN codes.~~
- Set up caching functions to minimise generation, especially with more static webpages (eg locality navigation)
- ~~Change titling such that we have indicator & common name with street and landmark as subtitles. Some places will look weird, especially with city centre stops in South Yorkshire, but it should look better for most areas.~~
- Add a stop area page with either:
    - ~~list of stops within area~~
    - Live bus times for each stop within area. They should be hidden by default, with only one stop being updated, if the number of stops within area exceeds 2.
    - The TLNDS would be really useful in getting list of services for each stop.
    - Add breadcrumbs. Requires working out which locality from list of stops within area, eg (this would be easier to do during population instead of live data retrieval)

```sql
WITH count_stops AS (
      SELECT sa.code AS a_code,
             sp.locality_code AS l_code,
             COUNT(sp.atco_code) AS n_stops
        FROM stop_area AS sa
             INNER JOIN stop_point as sp
                     ON sp.stop_area_code = sa.code
    GROUP BY sa.code, sp.locality_code
)
SELECT a.a_code AS stop_area_code,
       a.l_code AS locality_code
  FROM count_stops AS a
       INNER JOIN (
             SELECT a_code,
                    l_code,
                    MAX(n_stops) AS m_stops
               FROM count_stops
           GROUP BY a_code, l_code
       ) AS b
               ON a.a_code = b.a_code AND
                  a.l_code = b.l_code AND
                  a.n_stops = b.m_stops;
```

Or in Python (SQLAlchemy):

```python
from nextbus import db, models
from sqlalchemy import and_, func
# Find locality codes as modes of stop points within each stop area.
# Stop areas are repeated if there are multiple modes.
c_stops = (db.session.query(models.StopArea.code.label('a_code'),
                            models.StopPoint.locality_code.label('l_code'),
                            func.count(models.StopPoint.atco_code).label('n_stops'))
           .join(models.StopArea.stop_points)
           .group_by(models.StopArea.code, models.StopPoint.locality_code)
          ).subquery()
m_stops = (db.session.query(c_stops.c.a_code, c_stops.c.l_code,
                            func.max(c_stops.c.n_stops).label('max_stops'))
           .group_by(c_stops.c.a_code, c_stops.c.l_code)
          ).subquery()

query_area_localities = (db.session.query(c_stops.c.a_code, c_stops.c.l_code)
                         .join(m_stops, and_(c_stops.c.a_code == m_stops.c.a_code,
                               c_stops.c.l_code == m_stops.c.l_code,
                               c_stops.c.n_stops == m_stops.c.max_stops))
                        ).all()
```

- What to do about deleted stops??
- Add natural sorting for stop indicators, such that for a bus interchange `Stand 5` will appear before `Stand 10` - under normal sorting rules the former will show up first. Would have to be done in Python if using SQLite3; should be possible in PostgreSQL thanks to use of regex expressions.
- ~~Move the `populate` command to a separate module and import it into the package somehow.~~ Need to be able to set default value such that `flask populate -n` will give a prompt to download the required data. Currently the `-n` option checks if given values do exist; would be better to move that into the actual functions themselves.
- ~~Add SQLAlchemy logging; this would help with optimising SQL queries.~~
- Change locality page to a mix of stop points and areas. Use a SQL query

```sql
SELECT 'stop_point' AS s_type,
       stop_point.atco_code AS code,
       stop_point.common_name AS name,
       stop_point.short_ind AS ind
  FROM stop_area
       LEFT OUTER JOIN stop_point
                    ON stop_area.code = stop_point.stop_area_code
 WHERE stop_point.locality_code = 'E0029996' AND stop_point.stop_area_code IS NULL
UNION
SELECT 'stop_area' AS stype,
       stop_area.code AS code,
       stop_area.name AS name,
       '' AS ind
  FROM stop_area, stop_point
 WHERE stop_point.locality_code = 'E0029996';
```

or in Python (SQLAlchemy):

```python
from sqlalchemy import implict_column
from nextbus import db, models
# Find all stop areas and all stop points _not_ associated with a stop area
# TODO: Adjust locality page to include stop areas
table_name = lambda m: literal_column("'%s'" % m.__tablename__)
stops = (db.session.query(table_name(models.StopPoint).label('s_type'),
                          models.StopPoint.atco_code.label('code'),
                          models.StopPoint.common_name.label('name'),
                          models.StopPoint.short_ind.label('ind'))
         .outerjoin(models.StopPoint.stop_area)
         .filter(models.StopPoint.locality_code == lty.code,
                 models.StopPoint.stop_area_code.is_(None))
        )
areas = (db.session.query(table_name(models.StopArea).label('s_type'),
                          models.StopArea.code,
                          models.StopArea.name,
                          literal_column("''").label('ind'))
         .filter(models.StopArea.locality_code == lty.code)
        )
query_stops = stops.union_all(areas).order_by('name')
list_stops = [r._asdict() for r in query_stops.all()]
```

- ~~**Fix issue where setting FLASK_DEBUG to 1 breaks the CLI program on Windows**.~~ See github.com/pallets/werkzeug/issues/1136 - seems to be an issue with setuptools-created exes on Windows. *Symptom fixed by adding a `__main__.py` to the `nextbus` module which is identical in functionality to the `nxb` command. Just run it with `python -m nextbus [COMMAND]`.*

```
SyntaxError: Non-UTF-8 code starting with '\x90' in file C:\Miniconda3\envs\NxB\Scripts\nb.exe on line 1, but no encoding declared; see http://python.org/dev/peps/pep-0263/ for details
```

- Change options of `populate` command, *again*.
    - `-g` to download NPTG data.
    - `-G` with path to use file.
    - `-m` to use default JSON file for modifications.
    - `-n` to download NaPTAN data.
    - `-N` with path to use file.
    - `-p` to download NSPL data.
    - `-P` with path to use file.

```bash
nxb -gmnp                                                    # Download files
nxb -G temp/NPTG.xml -m -N temp/Naptan.xml -P temp/nspl.json # Use files
```
