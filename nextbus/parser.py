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
    string = str(query)
    open_p = 0
    # Remove any opening parentheses from end of string
    while string[-1] == opening:
        string = string[:-1]
    for i, char in enumerate(string):
        if char == opening:
            open_p += 1
        elif char == closing:
            open_p -= 1
        if open_p < 0:
            # Remove the stray closing parenthesis and try again
            cut_string = string[:i] + string[i+1:]
            new_query = _fix_parentheses(cut_string, opening, closing)
            break
    else:
        # Check if the parentheses are closed - add extra ones if necessary
        new_query = string + open_p * closing if open_p > 0 else string

    return new_query


class Operator(object):
    """ Base class for operators in a search query. """
    operator = None
    rank = None
    operands = list()

    def __init__(self):
        if self.operator is None or self.rank is None:
            raise NotImplementedError("The operator and rank must be defined "
                                      "with a new subclass.")

    def combine_operands(self):
        """ Returns sequence of operands converted to strings with the
            stringify method.
        """
        sequence = []
        for op in self.operands:
            try:
                if self.rank > op.rank:
                    # Inner operand is lower ranked, therefore needs to be
                    # wrapped in parentheses
                    string = '(%s)' % op.stringify() 
                else:
                    string = op.stringify()
            except AttributeError:
                # No stringify method, therefore a string
                string = op
            sequence.append(string)

        return sequence


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
        return self.operator + self.combine_operands()[0]


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
        return self.operator.join(self.combine_operands())


class At(BinaryOperator):
    """ Unary 'at' operator, to identify places. """
    operator = '@'
    rank = 0

    def stringify(self):
        """ Returns a tuple of two strings - one for stops/places and another
            for areas.
        """
        return tuple(self.combine_operands())


class Not(UnaryOperator):
    """ Unary NOT operator. """
    operator = '!'
    rank = 2


class And(BinaryOperator):
    """ Binary AND operator. """
    operator = '&'
    rank = 1


class Or(BinaryOperator):
    """ Binary OR operator. """
    operator = '|'
    rank = 0


class TSQueryParser(object):
    """ Class to parse query strings to make them suitable for the PostgreSQL
        ``to_tsquery()`` function.

        The PostgreSQL function accepts the following operators:
        - ``&`` for AND between words
        - ``|`` for OR between words
        - ``!`` to exclude word from query
        - ``()`` to evaluate inner expressions separately.

        All operators must be explicit, that is, a search query ``foo bar``
        must be inputted as ``foo & bar``. This parser converts a search query
        into one that can be read by ``to_tsquery`` properly.

        The parser accepts the following operators:
        - ``not foobar`` or ``!foobar`` to exclude a word from searches
        - ``foo bar`` or ``foo & bar`` to include both words
        - ``foo or bar`` and ``foo | bar`` to use either words
        - ``foo (bar or baz)`` to evaluate the OR expression first
        - ``foo @ bar``, ``foo at bar``, ``foo, bar`` and ``foo in bar`` to
        create two expressions, each evaluated separately, such that place or
        area ``bar`` matches stops or places ``foo``.

        Spaces between words or parentheses are parsed as implicit AND
        expressions.
    """
    def __init__(self, use_logger=False):
        self.parser = self.create_parser()
        self.use_logger = use_logger

    def __repr__(self):
        return "<TSQueryParser(use_logger=%s)>" % self.use_logger

    def __call__(self, search_query):
        """ Uses the parser and the to_string method to convert a search query
            to a string suitable for TSQuery objects.

            :param query: String from query.
            :returns: A string to be used in ``to_tsquery()``.
        """
        try:
            new_query = _fix_parentheses(search_query)
            output = self.parser.parseString(new_query)
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

    @staticmethod
    def create_parser():
        """ Creates the parser. """
        # Operators
        and_, or_ = pp.CaselessKeyword('and'), pp.CaselessKeyword('or')
        in_at = pp.CaselessKeyword('in') | pp.CaselessKeyword('at')
        op_not = pp.CaselessKeyword('not') | pp.Literal('!')
        op_and = and_ | pp.Literal('&')
        op_at = in_at | pp.Literal('@') | pp.Literal(',')
        op_or = or_ | pp.Literal('|')

        punctuation = ''.join(
            c for c in pp.printables
            if c not in pp.alphanums and c not in "!&|()@,"
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
        illegal_at = pp.Word(punctuation + "@,")
        word = ~and_ + ~or_ + pp.Word(pp.alphanums + pp.alphas8bit)
        # If search query is split into before and after @ operator, the first
        # part should not suppress or ignore 'at'/@ but the second part should
        search_bef_at = get_operators(~in_at + word, illegal, pp.Word("!&|"))
        search_aft_at = get_operators(word, illegal_at, pp.Word("!&|@,"))

        # Either 2 search terms plus @ operator or a single operator
        return (
            pp.Group(search_bef_at + op_at + search_aft_at).setParseAction(At)
            | search_bef_at + pp.Optional(pp.Word('@').suppress())
        ) + pp.stringEnd()
