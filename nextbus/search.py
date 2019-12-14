"""
Search functions for the nextbus package.
"""
import re

from flask import current_app

from nextbus import db, models


REGEX_CODE = re.compile(r"^\s*([A-Za-z\d]{5,12})\s*$")
REGEX_POSTCODE = re.compile(r"^\s*([A-Za-z]{1,2}\d{1,2}[A-Za-z]?)"
                            r"\s*(\d[A-Za-z]{2})\s*$")
PAGE_LENGTH = 25


class NoPostcode(Exception):
    """ Raised if a postcode was identified but it doesn't exist. """
    def __init__(self, query, postcode, msg=None):
        if msg is None:
            msg = f"Postcode {postcode!r} does not exist."
        super().__init__(msg)
        self.query = query
        self.postcode = postcode


class InvalidParameters(Exception):
    """ Raised if invalid parameters are given by a search query request. """
    def __init__(self, query, param, values, msg=None):
        if msg is None:
            msg = (
                f"Parameter {param!r} for query {query!r} contained invalid "
                f"values {values!r}"
            )
        super().__init__(msg)
        self.query = query
        self.param = param
        self.values = values


class SearchNotDefined(Exception):
    """ Raised if parsed search query is not defined enough, ie it does not
        have terms that restricts the scope of the query. """
    def __init__(self, query, msg=None):
        if msg is None:
            msg = f"Query {query!r} is not defined enough."
        super().__init__(msg)
        self.query = query
        self.not_defined = True


def search_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or None if no match is found.

        :param query: Query text returned from search form.
        :returns: A StopPoint or Postcode object if either was found, else None.
        :raises NoPostcode: if a query was identified as a postcode but it does
        not exist.
    """
    found = None

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

    match_code = REGEX_CODE.match(query)
    if found is None and match_code:
        # Search NaPTAN code & ATCO code
        code = match_code.group(1)
        stop = (
            models.StopPoint.query.options(db.load_only("atco_code"))
            .filter((models.StopPoint.naptan_code == code.lower()) |
                    (models.StopPoint.atco_code == code.upper()))
            .one_or_none()
        )
        found = stop

    if found is not None:
        current_app.logger.debug(
            f"Search query {query!r} returned exact match {found!r}"
        )

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

    try:
        page_num = int(page)
    except TypeError:
        raise InvalidParameters(query, "page", page)

    if groups is not None and set(groups) - models.FTS.GROUP_NAMES.keys():
        raise InvalidParameters(query, "group", groups)

    search = models.FTS.search(query, groups, admin_areas)
    if search is None:
        raise SearchNotDefined(query)

    result = search.paginate(page_num, per_page=PAGE_LENGTH, error_out=False)

    count = result.total
    current_app.logger.debug(
        f"Search query {query!r} returned {count} result"
        f"{'s' if count != 1 else ''}"
    )

    return result


def filter_args(query, admin_areas=None):
    """ Find all matching result groups and admin areas to be filtered.

    :param query: Query text returned from search form.
    :param admin_areas: Filter possible groups with pre-selected admin areas.
    :returns: Tuple of two dicts: the result groups and administrative areas
    """
    result = models.FTS.matching_groups(query, admin_areas)
    if result is not None:
        groups, args = result
    else:
        raise SearchNotDefined(query)

    current_app.logger.debug(
        f"Search query {query!r} have possible filters {groups!r} and {args!r}"
    )

    return groups, args
