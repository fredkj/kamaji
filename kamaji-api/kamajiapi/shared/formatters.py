import re
from string import printable


def querify(**kwargs):
    """
    Turn the kwargs into a string suitable for passing as the query part of
    an url.
    :param kwargs: The kwargs to querify.
    :return: String representation of the kwargs.
    """
    queries = ['{0}={1}'.format(key, value) for key, value in kwargs.items()]
    return '&'.join(queries)


def remove_hidden_chars(text):
    """
    Removes all hidden characters from a text for example to use in a url.
    :param text: Text to manipulate.
    :return: The text with all hidden characters removed.
    """
    return re.sub('[^{}]+'.format(printable), '', text)
