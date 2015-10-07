import sys

class PrassError(Exception):
    pass

PY2 = sys.version_info[0] == 2

if not PY2:
    py2_unicode_compatible = lambda x: x

    itervalues = lambda x: iter(x.values())
    iterkeys = lambda x: iter(x.keys())
    zip = zip
else:
    itervalues = lambda x: x.itervalues()
    iterkeys = lambda x: x.iterkeys()
    import itertools
    zip = itertools.izip

    def py2_unicode_compatible(cls):
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode("utf-8")
        return cls
