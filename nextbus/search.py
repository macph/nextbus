"""
Search functions for the nextbus package.
"""
import re
import reprlib

from flask import current_app

from nextbus import db, models, ts_parser


REGEX_POSTCODE = re.compile(r"^\s*([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)"
                            r"\s*(\d[A-Za-z]{2})\s*$")
PAGE_LENGTH = 25


class NoPostcode(Exception):
    """ Raised if a postcode was identified but it doesn't exist. """
    def __init__(self, query, postcode, msg=None):
        if msg is None:
            msg = "Postcode '%s' does not exist." % postcode
        super().__init__(msg)
        self.query = query
        self.postcode = postcode


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


def search_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or None if no match is found.

        :param query: Query text returned from search form.
        :returns: SearchResult object with stop or postcode.
        :raises NoPostcode: if a query was identified as a postcode but it does
        not exist.
    """
    match_postcode = REGEX_POSTCODE.match(query)

    if match_postcode:
        # Search postcode; make all upper and remove spaces first
        outward, inward = match_postcode.group(1), match_postcode.group(2)
        postcode = (
            models.Postcode.query.options(db.load_only("text"))
            .filter(models.Postcode.index == (outward + inward).upper())
            .one_or_none()
        )
        if postcode is None:
            raise NoPostcode(query, (outward + " " + inward).upper())
        found = postcode

    else:
        # Search NaPTAN code & ATCO code
        stop = (
            models.StopPoint.query.options(db.load_only("atco_code"))
            .filter((models.StopPoint.naptan_code == query.lower()) |
                    (models.StopPoint.atco_code == query.upper()))
            .one_or_none()
        )
        found = stop

    if found is not None:
        current_app.logger.debug("Search query %r returned exact match %r"
                                 % (query, found))

    return found


def search_all(query, groups=None, admin_areas=None, page=1):
    """ Searches for stops, postcodes and places, returning full data including
        area information.

        :param query: Query text returned from search form.
        :param groups: Iterable for groups of results eg 'area' or 'stop'
        :param admin_areas: Filters by administrative area.
        :param page: Page number for results.
        :returns: SearchResult object with stop, postcode or paginated list of
        results.
    """
    matching = search_code(query)
    if matching is not None:
        # Matching postcode or stop already found
        return matching

    # Else: do a full text search - format query string first
    parsed = ts_parser(query)

    try:
        page_num = int(page)
    except TypeError:
        raise InvalidParameters(query, "page", page)

    if groups is not None and set(groups) - models.FTS.GROUP_NAMES.keys():
        raise InvalidParameters(query, "group", groups)

    search = models.FTS.search(parsed, groups, admin_areas)
    result = search.paginate(page_num, per_page=PAGE_LENGTH, error_out=False)

    count = result.total
    current_app.logger.debug(
        "Search query %r parsed as %r and returned %s result%s" %
        (query, parsed.to_string(), count, "" if count == 1 else "s")
    )

    return result


def filter_args(query, admin_areas=None):
    """ Find all matching result groups and admin areas to be filtered.

    :param query: Query text returned from search form.
    :param admin_areas: Filter possible groups with pre-selected admin areas.
    :returns: Tuple of two dicts: the result groups and administrative areas
    """
    parsed = ts_parser(query)
    groups, args = models.FTS.matching_groups(parsed, admin_areas)

    current_app.logger.debug("Search query %r have possible filters %r and %r"
                             % (query, groups, args))

    return groups, args
