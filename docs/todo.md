# To do...

- Find out more about SQLite or PostgresSQL and convert NaPTAN data over to a 
SQL database for use by the website.
- Implement the NaPTAN and NPTG data in a SQLite database. Set up a script for
doing this work.
- Integrate NSPL data with NPTG, if that's possible.
- Set up the website.
```
Home Page: search for bus stop, route, etc
 |--About Page
 |--NaPTAN/SMS code direct
 |   |--Filter by bus route
 |--ATCOCode direct
 |   |--Filter by bus route
 |--Search for buses
     |--All bus stops in range of postcode
     |--All bus stops in range of lat/long
     |--All bus stops in range of bus stop
 |--Search bus routes
```
- Set up TransportAPI querying, convert to data to be used by the website. Make
a distinction between live and timetabled times.
- How to retrieve lat/long data?
- Settings per user (eg with cookies) - may want to start tracking once they
set up favourites or such?
- Get 2 database - static for all data such as postcodes and stops, and
users/dynamic for users, eg tracking and cookies.
- Should we set up the URLs such that we have `/stop?naptan=51201` or
`/list?postcode=W1A 1AA`, instead of `/naptan/51201` or `/postcode/W1A 1AA`?
- Check why the lat/long->OS grid calculations are off; try direct geodesic
calculations instead?