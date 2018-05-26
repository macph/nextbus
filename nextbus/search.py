"""
Search functions for the nextbus package.
"""
import collections
import re
import reprlib

from flask import current_app, request

from nextbus import db, models, ts_parser
from nextbus.parser import SET_ALPHANUM

TYPES = {"area", "place", "stop"}
REGEX_POSTCODE = re.compile(r"^\s*([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)"
                            r"\s*(\d[A-Za-z]{2})\s*$")
NAMES_ONLY = False
PAGE_LENGTH = 25


class NoPostcode(Exception):
    """ Raised if a postcode was identified but it doesn't exist. """
    def __init__(self, query, postcode, msg=None):
        if msg is None:
            msg = "Postcode '%s' does not exist." % postcode
        super().__init__(msg)
        self.query = query
        self.postcode = postcode


class QueryTooShort(Exception):
    """ Raised if query is too short. """
    def __init__(self, query, msg=None):
        if msg is None:
            msg = "Query %r is too short or has invalid characters" % query
        super().__init__(msg)
        self.query = query
        self.short = True


class InvalidParameters(Exception):
    """ Raised if invalid parameters are given by a search query request. """
    def __init__(self, query, param, values, msg=None):
        if msg is None:
            msg = ("Parameter %r for query %r contained invalid values %r"
                   % (param, query, values))
        super().__init__(msg)
        self.query = query
        self.param = param
        self.values = values


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


def search_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or None if no match is found.

        :param query: Query text returned from search form.
        :returns: SearchResult object with stop or postcode.
        :raises NoPostcode: if a query was identified as a postcode but it does
        not exist.
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
            raise NoPostcode(query, (outward + " " + inward).upper())
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


def search_all(query, types=None, admin_areas=None, page=1):
    """ Searches for stops, postcodes and places, returning full data including
        area information.

        :param query: Query text returned from search form.
        :param types: Iterable with values 'area', 'place' or 'stop'.
        :param admin_areas: Filters by administrative area.
        :param page: Page number for results.
        :returns: SearchResult object with stop, postcode or paginated list of
        results.
    """
    matching = search_code(query)
    if matching:
        result = matching
    else:
        # Else: do a full text search - format query string first
        parsed = ts_parser(query)
        res = models.FTS.search(parsed, types, admin_areas, NAMES_ONLY)
        page = res.paginate(page, per_page=PAGE_LENGTH, error_out=False)

        count = page.total
        current_app.logger.info(
            "Search query %r parsed as %r and returned %s result%s" %
            (query, parsed.to_string(), count, "" if count == 1 else "s")
        )
        result = SearchResult(list_=page)

    return result


def filter_args(query):
    """ Find all matching result types and admin areas to be filtered.

    :param query: Query text returned from search form.
    :returns: Tuple of two lists: the result types and administrative areas,
    with the latter a list of tuples.
    """
    parsed = ts_parser(query)
    types, args = models.FTS.matching_types(parsed, NAMES_ONLY)

    current_app.logger.info("Search query %r have possible filters %r and %r" %
                            (query, types, args))

    return types, args


def validate_characters(query):
    """ Strips out all punctuation and whitespace by using character sets and
        check if the remaining set has enough characters.
    """
    if not set(query) & SET_ALPHANUM:
        raise QueryTooShort(query)


def validate_params(query):
    """ Checks parameters given with search query and throw exception if they
        are invalid.

        :param query: Search query to be passed to exception.
        :returns: Arguments for searching created from query string as dict
        :raises InvalidParameters: Query string parameter contained invalid
        values
    """
    params = {}

    if request.args.get("type"):
        set_types = set(request.args.getlist("type"))
        invalid_types = set_types - TYPES
        if invalid_types:
            raise InvalidParameters(query, "type", invalid_types)
        params["types"] = list(set_types & TYPES)

    if request.args.get("area"):
        params["admin_areas"] = request.args.getlist("area")

    if request.args.get("page"):
        try:
            page_number = int(request.args.get("page"))
            if page_number < 1:
                raise ValueError
        except (TypeError, ValueError):
            raise InvalidParameters(query, "page", request.args.get("page"))
        else:
            params["page"] = page_number

    return params


def validate_after_search(query, types, areas):
    """ Validates parameters after querying results and list of matching areas
        and types.
    """
    invalid_types = set(request.args.getlist("type")) - types.keys()
    if invalid_types:
        raise InvalidParameters(query, "type", invalid_types)

    invalid_areas = set(request.args.getlist("areas")) - areas.keys()
    if invalid_areas:
        raise InvalidParameters(query, "area", invalid_areas)
