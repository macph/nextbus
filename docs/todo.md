# To do...

## Set up the website

`/` & `/home` **Home page**: search for bus stop, route, etc
- `/about` **About**: Stuff about me, github page, APIs used, framework used
- `/list` **List of regions**: List of all regions and their (admin) areas.
    - `/list/area/<code>` **List of districts/localities**: List of districts *or* localities in an area
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

### Changes to area list
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

## Migrate to PostgreSQL
Consider switching over to a PostgreSQL DB for compatibility with cloud providers and FT search.
- Install the `psycopg2` module to let SQLAlchemy interact with the PSQL server.
- Use extra features provided by PostgreSQL, such as `ON CONFLICT`:
```sql
INSERT INTO StopPoints (atco_code, naptan_code, last_modified ...)
VALUES ('490008978N1', '75463', '2017-11-21 16:53:00' ...)
ON CONFLICT stop_codes
DO UPDATE SET atco_code='490008978N1',
              naptan_code='75463',
              last_modified='2017-11-21 16:53:00',
              ...
WHERE StopPoints.last_modified < '2017-11-21 16:53:00';
```
- Consider getting 2 databases - static for all data such as postcodes and stops, and users/dynamic for users, eg tracking and cookies.
- Settings per user (eg with cookies) - may want to start tracking once they
set up favourites or such?
- Consider changing DB tables such that:
    - Harmonise names (mix of short and common names) - makes it easier to sort.
    - Add fields for colour - background and text/logo. See table.
    - Live tracking enabled areas - a whitelist (London, SY, GM, etc would qualify)
- With PSQL implemented, add proper search fields

## Styling website
- Create a webfont with icons: bus/tram, TfL roundel, arrows, search, refresh, etc. This would allow the bus/tram icons to be of different colours without having to use JS to modify the SVG colours.

### Admin area colours
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

## Responses for requests
- Change JS to report on live data status (timed out, server unavailable, can't reach API, etc)
- If no response is received:
    - Display message (timed out, unavailable, etc)
    - Change the time remaining by cutting off a minute off and any live times could be changed to timetabled alternative, or simulated with red text to indicate they are not tracked at present. This requires including _both_ live and timetabled times - use ISO formats and let JS do the minute calculations?


## What else?
- Set up caching functions to minimise generation, especially with more static webpages (eg locality navigation)
- Change titling such that we have indicator & common name with street and landmark as subtitles. Some places will look weird, especially with city centre stops in South Yorkshire, but it should look better for most areas.
- Add a stop area page with either:
    - list of stops within area
    - Live bus times for each stop within area. They should be hidden by default, with only one stop being updated, if the number of stops within area exceeds 2.
    - The TLNDS would be really useful in getting list of services for each stop.
- Sort out response handling for:
    - `stop_get_times()` POST response; need to pass on any errors from retrieving data to the JS
    - `LiveData` JS object; need to handle errors (eg 400, 404, 500) gracefully and let the user know.
    - `get_nextbus_times()` function for accessing API; need to pass on the right errors.