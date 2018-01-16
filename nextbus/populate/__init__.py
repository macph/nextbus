"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import re
import lxml.etree
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


class XMLDocument(object):
    """ Class to handle XML files and navigate through elements with XPath
        queries, with the assumption that there is a single namespace.

        :param file_name: XML file to be parsed.
        :param prefix: Prefix to be used while performing XPath queries.
    """
    # Ignores all words enclosed in quotes, spaces or prefixed with ':' or '@'.
    re_prefix = re.compile(r"(?<![:\"'@\s])(\b\w+\b)(?![:\"'\s])")

    def __init__(self, file_name, prefix='a'):
        self.data = lxml.etree.parse(file_name)
        self.prefix = prefix
        namespace = self.data.xpath("namespace-uri(.)")
        self.namespace = {self.prefix: namespace} if namespace else None

    def __call__(self, path, element=None, add_ns=True):
        """ Calls XPath query for a path, adding prefixes if necessary.

            :param path: XPath query with optional namespace prefixes.
            :param element: etree element to be queried. If argument is None
            the root self.data element is queried instead.
            :param add_ns: Add namespaces to XPath query if any are missing.
            :returns: List of etree elements matching query.
        """
        element = self.data if element is None else element
        new_path = self.add_namespace(path) if add_ns else path

        return element.xpath(new_path, namespaces=self.namespace)

    def add_namespace(self, path):
        """ Adds namespace prefixes to a XPath query before using lxml's xpath
            method.

            :param path: XPath query with optional namespace prefixes.
            :returns: New XPath query will namespace prefixes added.
            :raises ValueError: prefix given does not match one w
        """
        replace_ns = lambda s: "%s:%s" % (self.prefix, s.group())
        new_path = self.re_prefix.sub(replace_ns, path)

        return new_path

    def text(self, path, element=None, add_ns=True):
        """ Calls a XPath query and returns the text contained within the first
            element if it is the only matching result.

            :param path: XPath query with optional namespace prefixes.
            :param element: etree element to be queried. If argument is None
            the root self.data element is queried instead.
            :param add_ns: Add namespaces to XPath query if any are missing.
            :returns: Text content of single element matching query.
            :raises ValueError: Multiple or no elements found.
        """
        nodes = self(path, element, add_ns)
        if len(nodes) == 1:
            result = getattr(nodes[0], 'text', nodes[0])
        elif len(nodes) > 1:
            element = self.data if element is None else element
            raise ValueError("Multiple elements matching XPath query %r for "
                             "element %r." % (path, element))
        else:
            raise ValueError("No elements match XPath query %r for element "
                             "%r." % (path, element))

        return result

    def iter_text(self, path, elements, add_ns=True):
        """ Iterates over a list of elements with the same XPath query,
            returning a list of text values.

            :param path: XPath query with optional namespace prefixes.
            :param elements: List of elements to be iterated over.
            :param add_ns: Add namespaces to XPath query if any are missing.
            :returns: List of strings corresponding to text content in matched
            elements.
        """
        new_path = self.add_namespace(path) if add_ns else path

        return (self.text(new_path, element=node, add_ns=False)
                for node in elements)

    def dict_text(self, dict_paths, element=None, add_ns=True):
        """ Returns a dict of text values obtained from processing a dict with
            XPath queries as values for a single element.

            :param dict_paths: A dictionary with XPath queries as values.
            :param element: etree element to be queried. If argument is None
            the root self.data element is queried instead.
            :param add_ns: Add namespaces to XPath queries if any are missing.
            :returns: Another dictionary, with the same keys, with text
            content from each matched element.
        """
        if add_ns:
            paths = {k: self.add_namespace(v) for k, v in dict_paths.items()}
        else:
            paths = dict_paths

        result = {}
        for arg, path in paths.items():
            try:
                text = self.text(path, element, add_ns=False)
            except ValueError as err:
                if "No elements" in str(err):
                    text = None
                else:
                    raise
            result[arg] = text

        return result


def capitalise(string):
    """ Capitalises every word in a string, include these enclosed within
        brackets and excluding apostrophes.
    """
    list_words = string.lower().split()
    for _w, word in enumerate(list_words):
        for _c, char in enumerate(word):
            if char.isalpha():
                list_words[_w] = word[:_c] + char.upper() + word[_c+1:]
                break
    return ' '.join(list_words)
