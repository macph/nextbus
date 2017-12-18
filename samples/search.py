"""
Search functions for the nextbus package.
"""
import sys
import pyparsing as pp
from collections import defaultdict

from nextbus import db, create_app
from nextbus.models import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, Postcode
)

# TODO: Fix the issues with broken parentheses

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
    """
    def __init__(self):
        self.parser = self.create_parser()

    @staticmethod
    def create_parser():
        """ Creates the parser. """
        not_, and_, or_ = map(pp.CaselessKeyword, ['not', 'and', 'or'])
        op_not = not_ | pp.Literal('!')
        op_and = and_ | pp.oneOf('& +')
        op_or = or_ | pp.oneOf('| ,')
        illegal = pp.Word(""""#$%'*-./:;<=>?@[\\]^_`{}~""").suppress()
        word = ~and_ + ~or_ + pp.Word(pp.alphanums)
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
                new_query = cls.fix_parentheses(query[:i] + query[i+1:],
                                                opening, closing)
                break
        else:
            # Check if the parentheses are closed - add extra ones if necessary
            if open_p > 0:
                new_query = query + closing * open_p
            else:
                new_query = query

        return new_query

    @classmethod
    def stringify(cls, result, separator=None):
        """ Recursive function that converts a list of strings to a single
            string, with each word separated by a single space if a separator is
            not specified. Nested lists are enclosed in parentheses.

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
                new_list.append('(%s)' % cls.stringify(j, separator))

        return sep.join(new_list)

    def __call__(self, query):
        """ Parses a search query.

            :param query: String from search query.
            :returns: ParseResults object with results from parsing.
        """
        return self.parser.parseString(query)

    def parse_query(self, search_query):
        """ Uses the parser and the stringify method to convert a search query
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

        return self.stringify(output, '')


def search_stops(query, parser=None):
    """ Searches for stops, postcodes and place that fit the query string. """
    if not ''.join(query.split()):
        raise ValueError("No suitable query was entered.")
    # Search NaPTAN code & ATCO code first
    q_stop = StopPoint.query.filter(
        db.or_(StopPoint.naptan_code == query.lower(),
               StopPoint.atco_code == query.upper())
    ).one_or_none()
    if q_stop is not None:
        return q_stop

    # Search postcode; make all upper and remove spaces first
    q_psc = Postcode.query.filter(
        Postcode.index == ''.join(query.upper().split())
    ).one_or_none()
    if q_psc is not None:
        return q_psc

    # Else: do a full text search - format query string first
    s_query = parser(query) if parser else query
    empty_col = db.literal_column("''")
    table_col = lambda m: db.literal_column("'%s'" % m.__tablename__)
    s_region = (db.session.query(table_col(Region).label('table_name'),
                                 Region.code.label('code'),
                                 Region.name.label('name'),
                                 empty_col.label('indicator'),
                                 empty_col.label('street'),
                                 empty_col.label('locality_name'),
                                 empty_col.label('admin_area'),
                                 empty_col.label('admin_area_name'))
                .filter(db.func.to_tsvector('english', Region.name)
                        .match(s_query, postgresql_regconfig='english'))
               )
    s_admin_area = (db.session.query(table_col(AdminArea).label('table_name'),
                                     AdminArea.code.label('code'),
                                     AdminArea.name.label('name'),
                                     empty_col.label('indicator'),
                                     empty_col.label('street'),
                                     empty_col.label('locality_name'),
                                     AdminArea.code.label('admin_area'),
                                     AdminArea.name.label('admin_area_name'))
                    .filter(db.func.to_tsvector('english', AdminArea.name)
                            .match(s_query, postgresql_regconfig='english'))
                   )
    s_district = (db.session.query(table_col(District).label('table_name'),
                                   District.code.label('code'),
                                   District.name.label('name'),
                                   empty_col.label('indicator'),
                                   empty_col.label('street'),
                                   empty_col.label('locality_name'),
                                   AdminArea.code.label('admin_area'),
                                   AdminArea.name.label('admin_area_name'))
                  .select_from(District)
                  .join(AdminArea, AdminArea.code == District.admin_area_code)
                  .filter(db.func.to_tsvector('english', District.name)
                          .match(s_query, postgresql_regconfig='english'))
                 )
    s_locality = (db.session.query(table_col(Locality).label('table_name'),
                                   Locality.code.label('code'),
                                   Locality.name.label('name'),
                                   empty_col.label('indicator'),
                                   empty_col.label('street'),
                                   empty_col.label('locality_name'),
                                   AdminArea.code.label('admin_area'),
                                   AdminArea.name.label('admin_area_name'))
                  .select_from(Locality)
                  .join(AdminArea, AdminArea.code == Locality.admin_area_code)
                  .outerjoin(Locality.stop_points)
                  .filter(db.func.to_tsvector('english', Locality.name)
                          .match(s_query, postgresql_regconfig='english'),
                          StopPoint.atco_code.isnot(None))
                 )
    s_stop_area = (db.session.query(table_col(StopArea).label('table_name'),
                                    StopArea.code.label('code'),
                                    StopArea.name.label('name'),
                                    empty_col.label('indicator'),
                                    empty_col.label('street'),
                                    Locality.name.label('locality_name'),
                                    AdminArea.code.label('admin_area'),
                                    AdminArea.name.label('admin_area_name'))
                   .select_from(StopArea)
                   .join(Locality, Locality.code == StopArea.locality_code)
                   .join(AdminArea, AdminArea.code == Locality.admin_area_code)
                   .filter(db.func.to_tsvector('english', StopArea.name)
                           .match(s_query, postgresql_regconfig='english'))
                  )
    s_stop = (db.session.query(table_col(StopPoint).label('table_name'),
                               StopPoint.atco_code.label('code'),
                               StopPoint.common_name.label('name'),
                               StopPoint.short_ind.label('indicator'),
                               StopPoint.street.label('street'),
                               Locality.name.label('locality_name'),
                               AdminArea.code.label('admin_area'),
                               AdminArea.name.label('admin_area_name'))
              .select_from(StopPoint)
              .join(Locality, Locality.code == StopPoint.locality_code)
              .join(AdminArea, AdminArea.code == Locality.admin_area_code)
              .filter(db.func.to_tsvector('english', StopPoint.common_name
                                          + ' ' + StopPoint.street)
                      .match(s_query, postgresql_regconfig='english'))
             )
    search = s_region.union(s_admin_area, s_district, s_locality, s_stop_area,
                            s_stop)

    result = defaultdict(list)
    for row in search.all():
        if row.table_name == 'region':
            result['regions'].append(row)
        else:
            result[row.admin_area_name].append(row)

    return result

def main(args=None):
    """ Main function. """
    if args is None:
        args = sys.argv
    parser = TSQueryParser()
    while True:
        query = input("\nEnter a query (or nothing to quit): ") if len(args) < 2 else args[1]
        if not query:
            break
        result = search_stops(query, parser.parse_query)
        if not result:
            print('No stops or places found.')
        elif isinstance(result, StopPoint) or isinstance(result, Postcode):
            print(result)
        else:
            if 'regions' in result.keys():
                print('\nRegions')
                for region in result.pop('regions'):
                    print(region)
            order = ['admin_area', 'district', 'locality', 'stop_area', 'stop_point']
            for area, list_places in result.items():
                print('\n' + area)
                for row in sorted(list_places, key=lambda x: order.index(x.table_name)):
                    print(row)
        if len(args) > 1:
            break


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        main()
