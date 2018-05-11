"""
Search functions for the nextbus package.
"""
import collections
import re
import reprlib

from flask import current_app

from nextbus import db, models, ts_parser


REGEX_POSTCODE = re.compile(r"^\s*([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)"
                            r"\s*(\d[A-Za-z]{2})\s*$")
LOCAL_LIMIT = 32
STOPS_LIMIT = 256


class SearchResult(object):
    """ Helper class to hold results of a search query, which can be either a
        stop point, a postcode or a list of results with names matching the
        query.
    """
    def __init__(self, stop=None, postcode=None, list_=None):
        # Check arguments
        if sum(i is not None for i in [stop, postcode, list_]) > 1:
            raise TypeError("At most one argument can be specified.")

        self.stop = stop
        self.postcode = postcode
        self.list = list_

    def __repr__(self):
        if self.stop is not None:
            return "<SearchResult(stop=%r)>" % self.stop
        elif self.postcode is not None:
            return "<SearchResult(postcode=%r)>" % self.postcode
        elif self.list is not None:
            return "<SearchResult(list=%s)>" % reprlib.repr(self.list)
        else:
            return "<SearchResult(None)>"

    def __bool__(self):
        """ Checks if result does exist. """
        return any(i is not None for i in
                   [self.stop, self.postcode, self.list])

    def is_stop(self):
        """ Checks if result is a stop point object. """
        return self.stop is not None

    def is_postcode(self):
        """ Checks if result is a postcode object. """
        return self.postcode is not None

    def is_list(self):
        """ Checks if result is a list. """
        return self.list is not None


class PostcodeException(Exception):
    """ Raised if a postcode was identified but it doesn't exist. """
    def __init__(self, query, postcode):
        super(PostcodeException, self).__init__()
        self.query = query
        self.postcode = postcode

    def __str__(self):
        return ("Postcode '%s' from query %r does not exist."
                % (self.postcode, self.query))


def search_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or None if no match is found.
    """
    postcode = REGEX_POSTCODE.match(query)
    if postcode:
        # Search postcode; make all upper and remove spaces first
        outward, inward = postcode.group(1), postcode.group(2)
        q_psc = (
            models.Postcode.query.options(db.load_only("text"))
            .filter(models.Postcode.index == (outward + inward).upper())
            .one_or_none()
        )
        found = SearchResult(postcode=q_psc)
        if not found:
            raise PostcodeException(query, (outward + " " + inward).upper())
    else:
        # Search NaPTAN code & ATCO code
        q_stop = (
            models.StopPoint.query.options(db.load_only("atco_code"))
            .filter(db.or_(models.StopPoint.naptan_code == query.lower(),
                           models.StopPoint.atco_code == query.upper()))
            .one_or_none()
        )
        found = SearchResult(stop=q_stop)

    if found:
        current_app.logger.info("Search query %r returned exact match %r"
                                % (query, found))

    return found


def search_full(query, area=True, place=True, stop=True, admin_areas=None):
    """ Searches for stops, postcodes and places, returning full data including
        area information.

        :param query: Query text returned from search form.
        :returns: SearchResult object with stop, postcode or list of results
        :raises ValueError: if a query without any words was submitted.
        :raises PostcodeException: if a query was identified as a postcode but
        it does not exist.
    """
    if not "".join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    matching = search_code(query)
    if matching:
        result = matching
    else:
        # Else: do a full text search - format query string first
        parsed = ts_parser(query)
        list_results = models.FTS.search(parsed, area, place, stop,
                                         admin_areas, names_only=False).all()

        dict_results = collections.defaultdict(list)
        for row in list_results:
            if row.table_name in ["admin_area", "district"]:
                dict_results["area"].append(row)
            elif row.table_name in ["stop_area", "stop_point"]:
                dict_results["stop"].append(row)
            elif row.table_name == "locality":
                dict_results["locality"].append(row)

        count = {k: len(v) for k, v in dict_results.items()}
        current_app.logger.info(
            "Search query %r parsed as %r and returned results %s" %
            (query, parsed.to_string(), count)
        )

        # Results were already ordered in SQL query; no need to sort lists
        if dict_results:
            result = SearchResult(list_=dict_results)
        else:
            result = SearchResult()

    return result
