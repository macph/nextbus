"""
Search query parser for the nextbus search module.
"""
import re

import pyparsing as pp
from flask import current_app


SET_ALPHANUM = set(pp.alphanums + pp.alphas8bit)
SET_PRINT = set(pp.printables + pp.alphas8bit + pp.punc8bit)
SET_PUNCT = (set(pp.printables) - set(pp.alphanums)) | set(pp.punc8bit)
# Captures all characters not within printable ASCII + extension, excluding <>
RE_INVALID_CHAR = re.compile(r"[^\x00-\x3b\x3d\x3f-\x7f\xa1-\xff]")


def _fix_parentheses(query, opening="(", closing=")"):
    """ Fixes open parentheses in queries by removing closing brackets or
        adding extra closing brackets.

        :param query: Search query as string.
        :param opening: Opening parenthesis to check, with '(' as default.
        :param closing: Closing parenthesis to check, with ')' as default.
        :returns: String with equal numbers of opening and closing parentheses.
    """
    string = str(query)
    open_p = 0
    # Remove any stray parentheses from either side
    string = string.lstrip(closing).rstrip(opening)

    for i, char in enumerate(string):
        if char == opening:
            open_p += 1
        elif char == closing:
            open_p -= 1
        if open_p < 0:
            # Remove the stray closing parenthesis and try again
            cut_string = string[:i] + string[i+1:]
            string = _fix_parentheses(cut_string, opening, closing)
            break
    else:
        # Check if the parentheses are closed - add extra ones if necessary
        if open_p > 0:
            string += closing * open_p

    return string


class ParseResult(object):
    """ Holds the parser results. """
    def __init__(self, result):
        self.result = result
        self.data = result[0] if len(result) == 1 else result

    def __repr__(self):
        return "<ParseResult(%r)>" % self.result

    def to_string(self, exclude_not=False):
        """ Returns the parser result as a single string. """
        _not = "!" if exclude_not else None
        try:
            string = self.data.stringify(exclude_op=_not)
        except AttributeError:
            # Already a string
            string = self.data

        return string

    def dump(self):
        return self.result.dump()


class Operator(object):
    """ Base class for operators in a search query. """
    operator, rank = None, None
    operands = list()

    def __init__(self):
        if self.operator is None or self.rank is None:
            raise NotImplementedError("The operator and rank must be defined "
                                      "with a new subclass.")

    def __repr__(self):
        return "%s:%r" % (self.operator, self.operands)

    def combine_operands(self, exclude_op=None):
        """ Returns sequence of operands converted to strings with the
            stringify method.

            :param exclude_op: List of operators, as strings, to exclude.
            :returns: List of strings converted from operands.
        """
        sequence = []
        for op in self.operands:
            try:
                if exclude_op is not None and op.operator in exclude_op:
                    # Exclude this term
                    continue
                string = op.stringify(exclude_op)
                if self.rank > op.rank:
                    # Lower ranked operands need to be wrapped in parentheses
                    string = "(" + string + ")"
            except AttributeError:
                # Should be an string already
                string = op
            sequence.append(string)

        return sequence

    def stringify(self):
        """ Stringify method required for joining operands with operators. """
        raise NotImplementedError


class UnaryOperator(Operator):
    """ Base class for unary operators in a search query. """
    def __init__(self, tokens):
        super(UnaryOperator, self).__init__()
        self.operands = [tokens[0][1]]

    def stringify(self, exclude_op=None):
        """ Returns the parsed query in string form. """
        return self.operator + self.combine_operands(exclude_op)[0]


class BinaryOperator(Operator):
    """ Base class for unary operators in a search query. """
    def __init__(self, tokens):
        super(BinaryOperator, self).__init__()
        self.operands = tokens[0][::2]

    def stringify(self, exclude_op=None):
        """ Returns the parsed query in string form. """
        return self.operator.join(self.combine_operands(exclude_op))


class Not(UnaryOperator):
    """ Unary NOT operator. """
    operator, rank = "!", 3


class FollowedBy(BinaryOperator):
    """ Binary operator for phrases. """
    operator, rank = "<->", 2

    def __init__(self, tokens):
        super(FollowedBy, self).__init__(tokens)
        # Override the operands
        self.operands = tokens[0].strip("'" + '"').split()


class And(BinaryOperator):
    """ Binary AND operator. """
    operator, rank = "&", 1


class Or(BinaryOperator):
    """ Binary OR operator. """
    operator, rank = "|", 0


def create_tsquery_parser():
    """ Creates a function to parse query strings to make them suitable for the
        PostgreSQL ``to_tsquery()`` function.

        The PostgreSQL function accepts the following operators:
        - ``()`` to evaluate inner expressions separately
        - ``<->`` to ensure words follow each other (eg phrase)
        - ``!`` to exclude word from query
        - ``&`` for AND between words
        - ``|`` for OR between words

        All operators used by the function must be explicit, that is, a search
        query ``foo bar`` must be read as ``foo & bar`` by `to_tsquery()`.

        The parser accepts the following operators:
        - ``foo (bar or baz)`` to evaluate the inner expression separately
        - ``foo "bar baz"`` for phrases
        - ``not foobar`` or ``!foobar`` to exclude a word from searches
        - ``foo bar`` or ``foo & bar`` to include both words
        - ``foo or bar`` and ``foo | bar`` to use either words

        Spaces between words or parentheses are parsed as implicit AND
        expressions.

        PostgreSQL's ``ts_rank()`` sometimes ignores operators within a tsquery
        value. It is uncertain whether this is intentional or not but it makes
        filtering by rank difficult when NOT operators are used. As a result
        a method is used to return a pair of strings - one to use for matching,
        and the other with all NOT terms excluded for ranking.
    """
    # Operators
    and_, or_ = pp.CaselessKeyword("and"), pp.CaselessKeyword("or")
    op_not = pp.CaselessKeyword("not") | pp.Literal("!")
    op_and = pp.Optional(and_ | pp.Literal("&"), default="&")
    op_or = or_ | pp.Literal("|")

    # Exclude operators and parentheses from words
    word_ = pp.Word("".join(SET_PRINT - set("()!&|")))
    word = ~and_ + ~or_ + word_

    # Declare empty parser and nested terms before before defining
    expression = pp.Forward()
    term_0 = (pp.quotedString.setParseAction(FollowedBy) |
              pp.Suppress("(") + expression + pp.Suppress(")") | word)

    term_not = pp.Group(op_not + term_0).setParseAction(Not)
    term_1 = term_not | term_0
    term_and = (pp.Group(term_1 + pp.OneOrMore(op_and + term_1))
                .setParseAction(And))
    term_2 = term_and | term_1
    term_or = (pp.Group(term_2 + pp.OneOrMore(op_or + term_2))
               .setParseAction(Or))
    term_3 = term_or | term_2

    expression <<= term_3 | pp.Empty()

    def parser(query, fix_parentheses=True):
        """ Search query parser function for converting queries to strings
            suitable for PostgreSQL's ``to_tsquery()``. Broken parentheses are
            fixed beforehand by default.
        """
        text = RE_INVALID_CHAR.sub(r"", query)
        if fix_parentheses:
            text = _fix_parentheses(text)

        try:
            output = expression.parseString(text)
        except pp.ParseException as err:
            current_app.logger.error("Parser ran into an error with the "
                                     "search query %r" % query, exc_info=1)
            raise ValueError("Query %r cannot be parsed.") from err

        if not output:
            raise ValueError("Query %r contained no valid words.")

        return ParseResult(output)

    return parser
