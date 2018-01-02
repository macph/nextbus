"""
Search functions for the nextbus package.
"""
import sys
import pyparsing as pp

from nextbus import db
from nextbus import models

# TODO: Is there a better/faster way of getting all Unicode characters?


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

        # Looping over all Unicode characters once
        alpha_num, punctuation = [], []
        for char in (chr(c) for c in range(sys.maxunicode)):
            if char.isalnum():
                alpha_num.append(char)
            elif not char.isspace():
                if char in '!&|()':
                    continue
                punctuation.append(char)

        illegal = pp.Word(''.join(punctuation)).suppress()
        word = ~and_ + ~or_ + pp.Word(''.join(alpha_num))
        replace = lambda op, s: op.setParseAction(pp.replaceWith(s))

        # Suppress illegal characters around words
        search_term = pp.Optional(illegal) + word + pp.Optional(illegal)
        search_expr = pp.infixNotation(search_term, [
            (replace(op_not, '!'), 1, pp.opAssoc.RIGHT),
            (pp.Optional(replace(op_and, '&'), default='&'), 2,
             pp.opAssoc.LEFT),
            (replace(op_or, '|'), 2, pp.opAssoc.LEFT)
        ]) + pp.StringEnd()

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


def search_exists(query, parser=None):
    """ Searches for stop, postcodes and places that do exist, without
        information on areas, before redirecting to a search results page with
        the full data.
    """
    if not ''.join(query.split()):
        raise ValueError("No suitable query was entered.")

    # Search stop points and postcodes for an exact match
    object_match = _check_code(query)
    if object_match:
        return object_match

    # Else: do a full text search - format query string first
    s_query = parser(query) if parser else query
    empty_col = db.literal_column("''")

    s_region = (
        db.session.query(
            models.Region.code.label('code')
        ).filter(db.func.to_tsvector('english', models.Region.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
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
                db.func.to_tsvector('english', models.StopPoint.common_name)
                .match(s_query, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(s_query, postgresql_regconfig='english')
            )
        )
    )
    search = s_region.union(s_admin_area, s_district, s_locality,
                            s_stop_area, s_stop)

    return search.all()


def search_full(query, parser=None):
    """ Searches for stops, postcodes and places, returning full data including
        area information.
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

    s_region = (
        db.session.query(
            _table_col(models.Region).label('table_name'),
            models.Region.code.label('code'),
            models.Region.name.label('name'),
            empty_col.label('indicator'),
            empty_col.label('street'),
            empty_col.label('locality_name'),
            empty_col.label('admin_area'),
            empty_col.label('admin_area_name')
        ).filter(db.func.to_tsvector('english', models.Region.name)
                 .match(s_query, postgresql_regconfig='english'))
    )
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
    s_stop_area = (
        db.session.query(
            _table_col(models.StopArea).label('table_name'),
            models.StopArea.code.label('code'),
            models.StopArea.name.label('name'),
            db.cast(db.func.count(models.StopArea.code), db.Text).label('indicator'),
            empty_col.label('street'),
            models.Locality.name.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.StopArea)
        .join(models.StopArea.stop_points)
        .join(models.Locality,
              models.Locality.code == models.StopArea.locality_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        .group_by(models.StopArea.code, models.Locality.code,
                  models.AdminArea.code)
        .filter(db.func.to_tsvector('english', models.StopArea.name)
                .match(s_query, postgresql_regconfig='english'))
    )
    s_stop = (
        db.session.query(
            _table_col(models.StopPoint).label('table_name'),
            models.StopPoint.atco_code.label('code'),
            models.StopPoint.common_name.label('name'),
            models.StopPoint.short_ind.label('indicator'),
            models.StopPoint.street.label('street'),
            models.Locality.name.label('locality_name'),
            models.AdminArea.code.label('admin_area'),
            models.AdminArea.name.label('admin_area_name')
        ).select_from(models.StopPoint)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_code)
        .join(models.AdminArea,
              models.AdminArea.code == models.Locality.admin_area_code)
        .filter(
            db.or_(
                db.func.to_tsvector('english', models.StopPoint.common_name)
                .match(s_query, postgresql_regconfig='english'),
                db.func.to_tsvector('english', models.StopPoint.street)
                .match(s_query, postgresql_regconfig='english')
            )
        )
    )
    search = s_region.union(s_admin_area, s_district, s_locality,
                            s_stop_area, s_stop)

    return search.all()
