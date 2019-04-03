"""
Search query parser for the nextbus search module.
"""
import re

import pyparsing as pp
from flask import current_app


SET_ALPHANUMERIC = set(pp.alphanums + pp.alphas8bit)
SET_PRINTABLE = set(pp.printables + pp.alphas8bit + pp.punc8bit)
SET_PUNCTUATION = (set(pp.printables) - set(pp.alphanums)) | set(pp.punc8bit)
# Captures all characters not within printable ASCII + extension, excluding <>
RE_INVALID_CHAR = re.compile(r"[^\x00-\x3b\x3d\x3f-\x7f\xa1-\xff]")


class QueryTooShort(Exception):
    """ Raised if query is too short. """
    def __init__(self, query, msg=None):
        if msg is None:
            msg = "Query %r is too short or has invalid characters" % query
        super().__init__(msg)
        self.query = query
        self.too_short = True


class SearchNotDefined(Exception):
    """ Raised if parsed search query is not defined enough, ie it does not
        have terms that restricts the scope of the query. """
    def __init__(self, query, msg=None):
        if msg is None:
            msg = "Query %r is not defined enough." % query
        super().__init__(msg)
        self.query = query
        self.not_defined = True


def validate_characters(query):
    """ Strips out all punctuation and whitespace by using character sets and
        check if the remaining set has enough characters.
    """
    if not set(query) & SET_ALPHANUMERIC:
        raise QueryTooShort(query)


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
    def __init__(self, query, result):
        self.query = query
        self.result = result
        self.data = result[0] if len(result) == 1 else result

    def __repr__(self):
        return "<ParseResult(%r)>" % self.result

    def to_string(self, defined=False, raise_undefined=True):
        """ Returns the full parser result as a single string.

            If defined is True, only the portion that is defined (ie have
            terms that restricts the scope of a search query) is included. For
            example, a search query 'Downing Street not Road' will be returned
            as 'Downing Street'.

            :param defined: If True, return only defined terms.
            :param raise_undefined: If True, raise SearchNotDefined if the
            query is too broad
            :returns: A string to be used in search query.
        """
        if not self.result:
            return None
        if raise_undefined and not self.check_tree():
            raise SearchNotDefined(self.query)
        try:
            return self.data.stringify(defined)
        except AttributeError:
            return self.data

    def check_tree(self):
        """ Examines the tree to see if all children have defined terms.

            A search query 'not Road' is too broad because it will search for
            everything not with term 'road'. A search query 'Downing not Road'
            is defined however because only items with term 'Downing' will
            match.
        """
        if not self.result:
            return False
        try:
            return self.data.defined()
        except AttributeError:
            return True

    def dump(self):
        """ Returns the parse result's dump, for debugging. """
        return self.result.dump()


class Operator(object):
    """ Base class for operators in a search query. """
    operator = None
    rank = None

    def __init__(self):
        if self.operator is None or self.rank is None:
            raise NotImplementedError("The operator and rank must be defined "
                                      "with a new subclass.")
        self.operands = []

    def __repr__(self):
        return "%s:%r" % (self.operator, self.operands)

    def combine_operands(self, defined=False, recursive=False):
        """ Returns sequence of operands converted to strings with the
            stringify method.

            :param defined: If True, check terms to ensure they are defined.
            :param recursive: If True, terms behind a NOT operator are
            evaluated to keep terms with double negatives.
            :returns: List of strings converted from operands.
        """
        sequence = []
        for op in self.operands:
            try:
                if defined and not op.defined(recursive):
                    # Term undefined; skip
                    continue
                string = op.stringify(defined, recursive)
                if not string:
                    continue
                if self.rank > op.rank:
                    # Lower ranked operands need to be wrapped in parentheses
                    string = "(" + string + ")"
            except AttributeError:
                # Should be an string already
                string = op
            sequence.append(string)

        return sequence

    def stringify(self, defined=False, recursive=False):
        """ Stringify method required for joining operands with operators. """
        raise NotImplementedError

    def defined(self, recursive=False):
        """ Checks if all children constitutes a definitive query. """
        raise NotImplementedError


class Not(Operator):
    """ Unary NOT operator. """
    operator, rank = "!", 3

    def __init__(self, tokens):
        super().__init__()
        self.operands = [tokens[0][1]]

    def stringify(self, defined=False, recursive=False):
        strings = self.combine_operands(defined, recursive)
        return self.operator + strings[0] if strings else ""

    def defined(self, recursive=False):
        """ All terms behind a NOT operator are undefined. If recursive is
            True, terms behind the NOT operator are evaluated to find terms
            with double negatives.
        """
        if recursive and hasattr(self.operands[0], "defined"):
            return not self.operands[0].defined(recursive)
        else:
            return False


class FollowedBy(Operator):
    """ Binary operator for phrases. """
    operator, rank = "<->", 2

    def __init__(self, tokens):
        super().__init__()
        self.operands = tokens[0].strip("\"'").split()

    def stringify(self, defined=False, recursive=False):
        return self.operator.join(self.combine_operands(defined, recursive))

    def defined(self, recursive=False):
        """ Defined if phrase is not empty. """
        return bool(self.operands)


class And(Operator):
    """ Binary AND operator. """
    operator, rank = "&", 1

    def __init__(self, tokens):
        super().__init__()
        self.operands = tokens[0][::2]

    def stringify(self, defined=False, recursive=False):
        return self.operator.join(self.combine_operands(defined, recursive))

    def defined(self, recursive=False):
        """ Only undefined if all terms are undefined. """
        return any(not hasattr(op, "defined") or op.defined(recursive)
                   for op in self.operands)


class Or(Operator):
    """ Binary OR operator. """
    operator, rank = "|", 0

    def __init__(self, tokens):
        super().__init__()
        self.operands = tokens[0][::2]

    def stringify(self, defined=False, recursive=False):
        return self.operator.join(self.combine_operands(defined, recursive))

    def defined(self, recursive=False):
        """ All terms must be defined. """
        return all(not hasattr(op, "defined") or op.defined(recursive)
                   for op in self.operands)


class Empty(Operator):
    """ Denotes an empty portion in a query, meant to be skipped over. """
    operator, rank = "", 0

    def __init__(self, _):
        super().__init__()
        self.operands = None

    def __repr__(self):
        return "Empty"

    def stringify(self, defined=False, recursive=False):
        return ""

    def defined(self, recursive=False):
        return False


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
        filtering by rank difficult when NOT operators are used. The
        ``to_string()`` method can return the defined portions of the query if
        required.
    """
    # Operators
    and_, or_ = pp.CaselessKeyword("and"), pp.CaselessKeyword("or")
    o_not = pp.CaselessKeyword("not") | pp.Literal("!")
    o_and = pp.Optional(and_ | pp.Literal("&"), default="&")
    o_or = or_ | pp.Literal("|")

    # Exclude operators and parentheses from words
    word_ = pp.Word("".join(SET_PRINTABLE - set("()!&|")))
    word = ~and_ + ~or_ + word_
    # Exclude binary operators and keywords at start of queries
    exclude = pp.Optional(pp.Word("|&") | and_ | or_).suppress()

    # Declare empty parser and nested terms before before defining
    expression = pp.Forward()
    term_0 = (
        pp.quotedString.setParseAction(FollowedBy) |
        pp.Suppress("(") + expression + pp.Suppress(")") |
        word
    )

    # Build the expression. NOT operators can be used recursively
    term_n = pp.Forward()
    term_n <<= pp.Group(o_not + (term_n | term_0)).setParseAction(Not)
    term_1 = term_n | term_0
    term_a = pp.Group(term_1 + pp.OneOrMore(o_and + term_1)).setParseAction(And)
    term_2 = term_a | term_1
    term_o = pp.Group(term_2 + pp.OneOrMore(o_or + term_2)).setParseAction(Or)
    term_3 = term_o | term_2

    expression <<= exclude + term_3 | pp.Empty().setParseAction(Empty)

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
            current_app.logger.error("Error with search query %r" % query,
                                     exc_info=1)
            raise ValueError("Query %r cannot be parsed.") from err

        return ParseResult(query, output)

    return parser
