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
- `/search/<string>` **Search**: Find an area, district, locality or stop name

## What else?
- Settings per user (eg with cookies) - may want to start tracking once they
set up favourites or such?
- Get 2 database - static for all data such as postcodes and stops, and
users/dynamic for users, eg tracking and cookies.
- Set up caching functions to minimise generation, especially with more static
webpages (eg locality navigation)
- Consider changing DB tables such that:
    - Harmonise names (mix of short and common names) - makes it easier to sort.
    - Add fields for colour - background and text/logo. See table.
    - Live tracking enabled areas - a whitelist (London, SY, GM, etc would qualify)
- Create a webfont with icons: bus/tram, TfL roundel, arrows, search, refresh, etc. This would allow the bus/tram icons to be of different colours without having to use JS to modify the SVG colours.
- Consider switching over to a PostgreSQL DB for compatibility with cloud providers and FT search.
    - Install the `psycopg2` module to let SQLAlchemy interact with the PSQL server.
- Change titling such that we have indicator & common name with street and landmark as subtitles. Some places will look weird, especially with city centre stops in South Yorkshire, but it should look better for most areas.
- Add a stop area page with either:
    - list of stops within area
    - Live bus times for each stop within area. They should be hidden by default, with only one stop being updated, if the number of stops within area exceeds 2.
    - The TLNDS would be really useful in getting list of services for each stop.

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
