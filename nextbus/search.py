"""
Search functions for the nextbus package.
"""
import pyparsing as pp
from flask import current_app
from nextbus import db
from nextbus import models

SEARCH_LIMIT = 2048


class LimitException(Exception):
    """ Raised if a search query returns too many results """
    def __init__(self, query, count):
        super(LimitException, self).__init__()
        self.query = query
        self.count = count
    
    def __str__(self):
        return ("Search result %r returned too many results (%d)"
                % (self.query, self.count))


def _get_unicode_characters():
    """ Loops through all Unicode characters, creating lists of alphanumeric
        and punctuation characters. Excludes characters used in parsing, ie
        !, &, | and ().
    """
    import sys

    alpha_num, punctuation = [], []
    for c in range(sys.maxunicode):
        char = chr(c)
        if char.isalnum():
            alpha_num.append(char)
        elif not char.isspace():
            if char in '!&|()':
                continue
            punctuation.append(char)

    return alpha_num, punctuation


class TSQueryParser(object):
    """ Class to parse query strings to make them suitable for the PostgreSQL
        ``to_tsquery()`` function.

        The ``to_tsquery`` function accepts the following operators:
        - ``&`` for AND between words
        - ``|`` for OR between words
        - ``!`` to exclude from query
        - ``()`` to evaluate inner expression separately.

        All operators must be explicit, that is, a search query ``foo bar``
        must be inputted as ``foo & bar``. This parser converts a search query
        into one that can be read by ``to_tsquery`` properly.

        The parser accepts the following operators:
        - ``not foobar`` or ``!foobar`` to exclude a word from searches
        - ``foo bar`` or ``foo & bar`` to include both words
        - ``foo or bar``, ``foo | bar`` or ``foo, bar`` to use either words
        - ``foo (bar or baz)`` to evaluate the OR expression first

        Spaces between words or parentheses are parsed as implicit AND
        expressions.
    """
    def __init__(self):
        self.parser = self.create_parser()

    @staticmethod
    def create_parser():
        """ Creates the parser. """
        # Operators
        not_, and_, or_ = map(pp.CaselessKeyword, ['not', 'and', 'or'])
        op_not = not_ | pp.Literal('!')
        op_and = and_ | pp.Literal('&')
        op_or = or_ | pp.oneOf('| ,')

        punctuation = ''.join(c for c in pp.printables
                              if c not in pp.alphanums and c not in '!&|()')
        illegal = pp.Word(punctuation + pp.punc8bit).suppress()
        word = ~and_ + ~or_ + pp.Word(pp.alphanums + pp.alphas8bit)
        replace = lambda op, s: op.setParseAction(pp.replaceWith(s))

        # Suppress unused characters around words
        search_term = pp.Optional(illegal) + word + pp.Optional(illegal)
        search_expr = pp.infixNotation(search_term, [
            (replace(op_not, '!'), 1, pp.opAssoc.RIGHT),
            (pp.Optional(replace(op_and, '&'), default='&'), 2,
             pp.opAssoc.LEFT),
            (replace(op_or, '|'), 2, pp.opAssoc.LEFT)
        ]) + pp.Optional(pp.Word('!&|').suppress()) + pp.StringEnd()

        return search_expr

    @classmethod
    def fix_parentheses(cls, query, opening='(', closing=')'):
        """ Fixes open parentheses in queries by removing closing brackets or
            adding extra closing brackets.
        """
        open_p = 0
        for i, char in enumerate(query):
            if char == opening:
                open_p += 1
            if char == closing:
                open_p -= 1
            if open_p < 0:
                # Remove the stray closing parenthesis and try again
                new_query = cls.fix_parentheses(
                    query[:i] + query[i+1:], opening, closing
                )
                break
        else:
            # Check if the parentheses are closed - add extra ones if necessary
            if open_p > 0:
                new_query = query + closing * open_p
            else:
                new_query = query

        return new_query

    @classmethod
    def to_string(cls, result, separator=None):
        """ Recursive function that converts a list of strings to a single
            string, with each word separated by a single space if a separator
            is not specified. Nested lists are enclosed in parentheses.

            :param result: A list of strings.
            :param separator: A string separating each item in the list. By
            default, a single space is used.
            :returns: A single string.
        """
        if isinstance(result, str):
            return result

        new_list = []
        sep = ' ' if separator is None else separator
        for i, j in enumerate(result):
            if isinstance(j, str):
                new_list.append(j)
            else:
                new_list.append('(%s)' % cls.to_string(j, separator))

        return sep.join(new_list)

    def __call__(self, query):
        """ Parses a search query.

            :param query: String from search query.
            :returns: ParseResults object with results from parsing.
        """
        return self.parser.parseString(query)

    def parse_query(self, search_query):
        """ Uses the parser and the to_string method to convert a search query
            to a string suitable for TSQuery objects.

            :param query: String from query.
            :returns: A string to be used in ``to_tsquery()``.
        """
        try:
            new_query = self.fix_parentheses(search_query)
            output = self(new_query)
        except pp.ParseException as err:
            raise ValueError("Parser ran into an error with the search query "
                             "%r:\n%s" % (search_query, err)) from err
        output = output[0] if len(output) == 1 else output
        query_string = self.to_string(output, '')
        current_app.logger.debug(
            "Search query %r parsed as\n%r\nand formatted as %r"
            % (search_query, output, query_string)
        )
        return self.to_string(output, '')


def _check_code(query):
    """ Queries stop points and postcodes to find an exact match, returning
        the model object, or None if no match is found.
    """
    # Search NaPTAN code & ATCO code first
    q_stop = models.StopPoint.query.filter(
        db.or_(models.StopPoint.naptan_code == query.lower(),
               models.StopPoint.atco_code == query.upper())
    ).one_or_none()
    if q_stop is not None:
        return q_stop

    # Search postcode; make all upper and remove spaces first
    q_psc = models.Postcode.query.filter(
        models.Postcode.index == ''.join(query.upper().split())
    ).one_or_none()
    if q_psc is not None:
        return q_psc


def _table_col(model):
    """ Helper function to create column with name of table. """
    return db.literal_column("'%s'" % model.__tablename__)


def search_exists(query, parser=None, raise_exception=True):
    """ Searches for stop, postcodes and places that do exist, without
        information on areas, before redirecting to a search results page with
        the full data.

        :param parser: Parser to use when searching for all results with
        PostgreSQL's full text search.
        :param raise_exception: Set to raise an exception when too many results
        are returned.
    """
    if not ''.join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    object_match = _check_code(query)
    if object_match:
        return object_match

    # Else: do a full text search - format query string first
    s_query = parser(query) if parser else query

    s_admin_area = (
        db.session.query(
            models.AdminArea.code.label('code')
        ).filter(db.func.to_tsvector('english', models.AdminArea.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    s_district = (
        db.session.query(
            models.District.code.label('code')
        ).filter(db.func.to_tsvector('english', models.District.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    s_locality = (
        db.session.query(
            models.Locality.code.label('code')
        ).outerjoin(models.Locality.stop_points)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(s_query, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    )
    s_stop_area = (
        db.session.query(
            models.StopArea.code.label('code')
        ).filter(db.func.to_tsvector('english', models.StopArea.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    s_stop = (
        db.session.query(
            models.StopPoint.atco_code.label('code')
        ).filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(s_query, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(s_query, postgresql_regconfig='english')
            )
        )
    )
    search = s_admin_area.union(s_district, s_locality, s_stop_area, s_stop)

    results = search.all()
    if raise_exception and len(results) > SEARCH_LIMIT:
        raise LimitException(s_query, len(results))

    return results


def search_full(query, parser=None, raise_exception=True):
    """ Searches for stops, postcodes and places, returning full data including
        area information.

        :param parser: Parser to use when searching for all results with
        PostgreSQL's full text search.
        :param raise_exception: Set to raise an exception when too many results
        are returned.
    """
    if not ''.join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    obj = _check_code(query)
    if obj:
        return obj

    # Else: do a full text search - format query string first
    s_query = parser(query) if parser else query
    empty_col = db.literal_column("''")

    s_admin_area = (
        db.session.query(
            _table_col(models.AdminArea).label('table_name'),
            models.AdminArea.code.label('code'),
            models.AdminArea.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).filter(db.func.to_tsvector('english', models.AdminArea.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
    s_district = (
        db.session.query(
            _table_col(models.District).label('table_name'),
            models.District.code.label('code'),
            models.District.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.District)
        .join(models.AdminArea,
              models.AdminArea.code == models.District.admin_area_code)
        .filter(db.func.to_tsvector('english', models.District.name)
                .match(s_query, postgresql_regconfig='english'))
    )
    s_locality = (
        db.session.query(
            _table_col(models.Locality).label('table_name'),
            models.Locality.code.label('code'),
            models.Locality.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.Locality)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        .outerjoin(models.Locality.stop_points)
        .filter(db.func.to_tsvector('english', models.Locality.name)
                .match(s_query, postgresql_regconfig='english'),
                models.StopPoint.atco_code.isnot(None))
    )
    # Subquery required to count number of stops in stop area and group by stop
    # area code before joining with locality and admin area
    sub_stop_area = (
        db.session.query(
            models.StopArea.code.label('code'),
            models.StopArea.name.label('name'),
            models.StopArea.admin_area_code.label('admin_area'),
            models.StopArea.locality_code.label('locality'),
            db.cast(db.func.count(models.StopArea.code), db.Text).label('ind'),
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code)
        .filter(db.func.to_tsvector('english', models.StopArea.name)
                .match(s_query, postgresql_regconfig='english'))
    ).subquery()
    s_stop_area = (
        db.session.query(
            _table_col(models.StopArea).label('table_name'),
            sub_stop_area.c.code.label('code'),
            sub_stop_area.c.name.label('name'),
            sub_stop_area.c.ind.label('indicator'),
            empty_col.label('street'),
            db.func.coalesce(models.Locality.name.label('locality_name'), ''),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(sub_stop_area)
        .outerjoin(models.Locality,
                   models.Locality.code == sub_stop_area.c.locality)
        .join(models.AdminArea,
              models.AdminArea.code == sub_stop_area.c.admin_area)
    )
    s_stop = (
        db.session.query(
            _table_col(models.StopPoint).label('table_name'),
            models.StopPoint.atco_code.label('code'),
            models.StopPoint.name.label('name'),
            models.StopPoint.short_ind.label('indicator'),
            models.StopPoint.street.label('street'),
            models.Locality.name.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.StopPoint)
        .outerjoin(models.StopArea,
                   models.StopArea.code == models.StopPoint.stop_area_code)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        # Include stops with name or street matching query but exclude these
        # within areas that have already been found - prevent duplicates
        .filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.name)
                .match(s_query, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(s_query, postgresql_regconfig='english')
            ),
            db.not_(
                db.and_(
                    models.StopPoint.stop_area_code.isnot(None),
                    db.func.to_tsvector('english', models.StopArea.name)
                    .match(s_query, postgresql_regconfig='english')
                )
            )
        )
    )
    search = s_admin_area.union(s_district, s_locality, s_stop_area, s_stop)

    results = search.all()
    if raise_exception and len(results) > SEARCH_LIMIT:
        raise LimitException(s_query, len(results))

    return results
