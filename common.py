import sys

from click.exceptions import ClickException

class PrassError(ClickException):
    pass

PY2 = sys.version_info[0] == 2

if not PY2:
    py2_unicode_compatible = lambda x: x

    itervalues = lambda x: iter(x.values())
    iteritems = lambda x: iter(x.items())
    iterkeys = lambda x: iter(x.keys())
    zip = zip
    map = map
else:
    itervalues = lambda x: x.itervalues()
    iteritems = lambda x: x.iteritems()
    iterkeys = lambda x: x.iterkeys()
    import itertools
    zip = itertools.izip
    map = itertools.imap

    def py2_unicode_compatible(cls):
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode("utf-8")
        return cls
