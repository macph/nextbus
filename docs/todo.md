# To do...

- Find out more about SQLite or PostgresSQL and convert NaPTAN data over to a 
SQL database for use by the website.
- Implement the NaPTAN and NPTG data in a SQLite database. Set up a script for
doing this work.
- Integrate NSPL data with NPTG, if that's possible.
- Set up the website.
```
Home Page: search for bus stop, route, etc
 ├─ About Page
 ├─ NaPTAN/SMS code direct
 │   └─ Filter by bus route
 ├─ ATCOCode direct
 │   └─ Filter by bus route
 ├─ Search for buses
 │   ├─ All bus stops in range of postcode
 │   ├─ All bus stops in range of lat/long
 │   └─ All bus stops in range of bus stop
 └─ Search bus routes
```
- How to retrieve lat/long data? Set up a JS function, and have it operate upon
pressing a button.
- Settings per user (eg with cookies) - may want to start tracking once they
set up favourites or such?
- Get 2 database - static for all data such as postcodes and stops, and
users/dynamic for users, eg tracking and cookies.
- How to handle stop points without NaPTAN codes? Best solution would be to
drop all entries with no NaPTAN codes.
- Refine templates further such that the list of stops for localities,
postcodes and locations all come from the same template, with a list of stop
points as an object. Same goes for live times for ATCO and NaPTAN codes.
- GET SOME TESTING DONE ::
- Clicking on region in the breadcrumbs should lead to the correct heading in
the region page; the `url_for()` function has a keyword argument `_anchor`
which adds a fragment identifier (`#`). Need to find out how to make the jump
to the correct heading -- use JS?
- Set up caching functions to find 