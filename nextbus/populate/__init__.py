"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import re
import functools
import lxml.etree as et
import click


NXB_URI = r"http://nextbus.org/functions"


def progress_bar(iterable, **kwargs):
    """ Returns click.progressbar with specific options. """
    return click.progressbar(
        iterable=iterable,
        bar_template="%(label)-32s [%(bar)s] %(info)s",
        show_pos=True,
        width=50,
        **kwargs
    )


def element_text(function):
    """ Converts XPath query result to a string by taking the text content from
        the only element in list before passing it to the extension function.
        If the XPath query returned nothing, the wrapped function will return
        None.
    """
    @functools.wraps(function)
    def _function_with_text(instance, context, result, *args, **kwargs):
        if len(result) == 1:
            return function(instance, context, result[0].text, *args, **kwargs)
        elif len(result) > 1:
            raise ValueError("XPath query returned multiple elements.")
        else:
            return None

    return _function_with_text


class ExtFunctions(object):
    """ Extension for modifying data in NaPTAN/NPTG data. """

    @element_text
    def replace(self, _, result, original, substitute):
        """ Replace substrings within content. """
        return result.replace(original, substitute)

    @element_text
    def upper(self, _, result):
        """ Convert all letters in content to uppercase. """
        return result.upper()

    @element_text
    def lower(self, _, result):
        """ Convert all letters in content to lowercase. """
        return result.lower()

    @element_text
    def remove_spaces(self, _, result):
        """ Remove all spaces from content. """
        return ''.join(result.strip())

    @element_text
    def capitalize(self, _, result):
        """ Capitalises every word in a string, include these enclosed within
            brackets and excluding apostrophes.
        """
        list_words = result.lower().split()
        for _w, word in enumerate(list_words):
            for _c, char in enumerate(word):
                if char.isalpha():
                    list_words[_w] = word[:_c] + char.upper() + word[_c+1:]
                    break
        return ' '.join(list_words)


nxb_xml_ext = et.Extension(ExtFunctions(), None, ns=NXB_URI)
