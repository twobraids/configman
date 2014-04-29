from configman.converters import to_str

classes = {}

class DontCare(object):
    def __init__(self, value):
        self._value = value
    def __str__(self):
        return to_str(self._value)
    def __getattr__(self, key):
        return getattr(self._value, key)
    def __call__(self, *args, **kwargs):
        return self._value(*args, **kwargs)
    def __iter__(self):
        for x in self._value:
            yield x


def dont_care(value):
    value_type = type(value)
    print 'dont_care', value, value_type
    try:
        result = classes[value_type](value)
        print "  ", result
        return result
    except KeyError:
        try:
            class X(value_type):
                @classmethod
                def __hash__(kls):
                    return hash(kls.__name__)
                def append(self, item):
                    self.modified = True
                    return super(X, self).append(item)
            X.__name__ = 'DontCareAbout_%s' % to_str(value_type)

        except TypeError:
            X = DontCare
        classes[value_type] = X
        return X(value)

