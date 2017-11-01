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
- Refine templates further such that the list of stops for localities,
postcodes and locations all come from the same template, with a list of stop
points as an object. Same goes for live times for ATCO and NaPTAN codes.
- Set up caching functions to minimise generation, especially with more static
webpages (eg locality navigation)
- Add ability to request (or refuse) live NextBuses data; would be good idea to
whitelist admin areas such that trams and specific areas will only get
timetabled data  (and a warning that such info is not live).
    - Do this by adding 'live_data' field to Admin areas.
- Consider changing DB tables such that:
    - Short version of indicator for labelling.
-