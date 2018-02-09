# -*- coding: utf-8 -*-
from itertools import cycle, islice


def roundrobin(*iterables):
    """
    roundrobin('ABC', 'D', 'EF') --> A D E B F C
    Recipe credited to George Sakkis
    """
    pending = len(iterables)
    nexts = cycle(iter(it).next for it in iterables)
    while pending:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            pending -= 1
            nexts = cycle(islice(nexts, pending))


def roundrobin_perpetual(*iterables):
    """
    roundrobin_perpetual('ABC', 'D', 'EF') --> A D E B F C ...
    """
    while True:
        for item in roundrobin(*iterables):
            yield item
