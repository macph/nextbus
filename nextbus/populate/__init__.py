"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import re
import click


def progress_bar(iterable, **kwargs):
    """ Returns click.progressbar with specific options. """
    return click.progressbar(
        iterable=iterable,
        bar_template="%(label)-32s [%(bar)s] %(info)s",
        show_pos=True,
        width=50,
        **kwargs
    )


class XPath(object):
    """ Helper class for XPath queries in a dataset, with the assumption that
        all sub elements have the same namespace. Adds prefixes to each XPath
        query automatically.
    """
    # Ignores all words enclosed in quotes, spaces or prefixed with ':' or '@'.
    re_prefix = re.compile(r"(?<![:\"'@\s])(\b\w+\b)(?![:\"'\s])")

    def __init__(self, element, prefix='a'):
        self.element = element
        self.prefix = prefix
        namespace = self.element.xpath("namespace-uri(.)")
        self.namespace = {self.prefix: namespace} if namespace else None

    def __call__(self, path, element=None):
        """ Calls XPath query for a path, adding prefixes if necessary """
        new_path = self.re_prefix.sub(lambda s: "%s:%s" % (self.prefix, s.group()), path)
        element = self.element if element is None else element
        return element.xpath(new_path, namespaces=self.namespace)

    def text(self, path, element=None):
        """ Calls a XPath query and returns the text contained within the first
            element if it is the only matching result.
        """
        nodes = self(path, element)
        if len(nodes) == 1:
            return getattr(nodes[0], 'text', nodes[0])
        elif len(nodes) > 1:
            element = self.element if element is None else element
            raise ValueError("Multiple elements matching XPath query %r for "
                             "element %r." % (path, element))
        else:
            raise ValueError("No elements match XPath query %r for element "
                             "%r." % (path, element))

    def iter_text(self, path, elements):
        """ Iterates over a list of elements with the same XPath query,
            returning a list of text values.
        """
        return [self.text(path, element=node) for node in elements]

    def dict_text(self, dict_paths, element=None):
        """ Returns a dict of text values obtained from processing a dict with
            XPath queries as values for a single element. If a query returns no
            elements, the key is assigned value None.
        """
        result = {}
        for arg, path in dict_paths.items():
            try:
                text = self.text(path, element)
            except ValueError as err:
                if "No elements" in str(err):
                    text = None
                else:
                    raise ValueError from err
            result[arg] = text

        return result


def capitalise(string):
    """ Capitalises every word in a string, include these enclosed within
        brackets and excluding apostrophes.
    """
    list_words = string.lower().split()
    for w, word in enumerate(list_words):
        for c, char in enumerate(word):
            if char.isalpha():
                list_words[w] = word[:c] + char.upper() + word[c+1:]
                break
    return ' '.join(list_words)
