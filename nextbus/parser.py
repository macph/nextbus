"""
Search query parser for the nextbus search module.
"""
import pyparsing as pp
from flask import current_app


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


def _fix_parentheses(query, opening='(', closing=')'):
    """ Fixes open parentheses in queries by removing closing brackets or
        adding extra closing brackets.

        :param query: Search query as string.
        :param opening: Opening parenthesis to check, with '(' as default.
        :param closing: Closing parenthesis to check, with ')' as default.
        :returns: String with equal numbers of opening and closing parentheses.
    """
    open_p = 0
    for i, char in enumerate(query):
        if char == opening:
            open_p += 1
        elif char == closing:
            open_p -= 1
        if open_p < 0:
            # Remove the stray closing parenthesis and try again
            cut_string = query[:i] + query[i+1:]
            new_query = _fix_parentheses(cut_string, opening, closing)
            break
    else:
        # Check if the parentheses are closed - add extra ones if necessary
        if open_p > 0:
            new_query = query + open_p * closing
        else:
            new_query = query

    return new_query


class Operator(object):
    """ Base class for operators in a search query. """
    operator = None

    def __init__(self):
        if self.operator is None:
            raise NotImplementedError("The operator must be defined with a "
                                      "new subclass.")

    @staticmethod
    def to_string(operand):
        """ Converts an operand to string form using the stringify method. """
        try:
            return operand.stringify()
        except AttributeError:
            return operand


class UnaryOperator(Operator):
    """ Base class for unary operators in a search query. """
    operator = None

    def __init__(self, tokens):
        super(UnaryOperator, self).__init__()
        self.symbol = tokens[0][0]
        self.operands = [tokens[0][1]]

    def __repr__(self):
        return "%s:%r" % (self.operator, self.operands)

    def stringify(self):
        """ Returns the parsed query in string form. """
        return self.operator + self.to_string(self.operands[0])


class BinaryOperator(Operator):
    """ Base class for unary operators in a search query. """
    operator = None

    def __init__(self, tokens):
        super(BinaryOperator, self).__init__()
        self.symbol = tokens[0][1]
        self.operands = tokens[0][::2]

    def __repr__(self):
        return "%s:%r" % (self.operator, self.operands)

    def stringify(self):
        """ Returns the parsed query in string form. """
        return self.operator.join(self.to_string(op) for op in self.operands)


class Not(UnaryOperator):
    """ Unary NOT operator. """
    operator = '!'


class At(BinaryOperator):
    """ Unary 'at' operator, to identify places. """
    operator = '@'

    def stringify(self):
        """ Returns a tuple of two strings - one for stops/places and another
            for areas.
        """
        return tuple(self.to_string(op) for op in self.operands)


class And(BinaryOperator):
    """ Binary AND operator. """
    operator = '&'


class Or(BinaryOperator):
    """ Binary OR operator. """
    operator = '|'


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
    def __init__(self, use_logger=False):
        self.parser = self.create_parser()
        self.use_logger = use_logger

    @staticmethod
    def create_parser():
        """ Creates the parser. """
        # Operators
        and_, or_ = pp.CaselessKeyword('and'), pp.CaselessKeyword('or')
        in_at = pp.CaselessKeyword('in') | pp.CaselessKeyword('at')
        op_not = pp.CaselessKeyword('not') | pp.Literal('!')
        op_and = and_ | pp.Literal('&')
        op_at = in_at | pp.Literal('@')
        op_or = or_ | pp.oneOf('| ,')

        punctuation = ''.join(
            c for c in pp.printables
            if c not in pp.alphanums and c not in '!&|()@'
        ) + pp.punc8bit

        def get_operators(word, exclude_characters, suppress_characters):
            """ Helper function to construct search query notation with
                operators.
            """
            # Suppress unused characters around words as well as operators on
            # end of strings, otherwise the parser will fail to find an operand
            # at the end of query and throw an exception
            search_term = (pp.Optional(exclude_characters.suppress()) + word
                           + pp.Optional(exclude_characters.suppress()))
            search_expr = pp.infixNotation(search_term, [
                (op_not, 1, pp.opAssoc.RIGHT, Not),
                (pp.Optional(op_and, default='&'), 2, pp.opAssoc.LEFT, And),
                (op_or, 2, pp.opAssoc.LEFT, Or)
            ]) + pp.Optional(suppress_characters.suppress())

            return search_expr

        # Operators 'and', 'at' and 'or' are excluded from words as not to be
        # part of search query. 'not' is higher in precedence and doesn't have
        # this problem
        illegal = pp.Word(punctuation)
        illegal_at = pp.Word(punctuation + '@')
        word = ~and_ + ~or_ + pp.Word(pp.alphanums + pp.alphas8bit)
        # If search query is split into before and after @ operator, the first
        # part should not suppress or ignore 'at'/@ but the second part should
        search_bef_at = get_operators(~in_at + word, illegal, pp.Word('!&|'))
        search_aft_at = get_operators(word, illegal_at, pp.Word('!&|@'))

        # Either 2 search terms plus @ operator or a single operator
        return (
            pp.Group(search_bef_at + op_at + search_aft_at).setParseAction(At)
            | search_bef_at + pp.Optional(pp.Word('@').suppress())
        ) + pp.stringEnd()

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
            new_query = _fix_parentheses(search_query)
            output = self(new_query)
        except pp.ParseException as err:
            raise ValueError("Parser ran into an error with the search query "
                             "%r:\n%s" % (search_query, err)) from err
        # Getting rid of outer list if one exists
        result = output[0] if len(output) == 1 else output
        try:
            tsquery = result.stringify()
        except AttributeError:
            tsquery = result

        if self.use_logger:
            current_app.logger.debug(
                "Search query %r parsed as\n%s\nand formatted as %r."
                % (search_query, output.dump(), tsquery)
            )
        return tsquery


def main():
    """ Testing... """
    parser = TSQueryParser()
    print("Enter a query (or nothing to quit):")
    query = input("> ")
    while query:
        try:
            new_q = _fix_parentheses(query)
            output = parser(new_q)
        except pp.ParseException as err:
            print("Problem with parser: %s" % err)
            query = input("> ")
            continue
        result = output[0] if len(output) == 1 else output
        try:
            tsquery = result.stringify()
        except AttributeError:
            tsquery = result
        print("Search query %r parsed as\n%s\nand formatted as %r."
              % (query, output.dump(), tsquery))

        query = input("> ")


if __name__ == "__main__":
    main()
