import types

from configman.converters import to_str, get_from_string_converter

classes = {}

class DontCare(object):
    def __init__(self, value):
        self.modified__ = False
        self._value = value
    def __str__(self):
        return to_str(self._value)
    def __getattr__(self, key):
        self.modified__ = True
        return getattr(self._value, key)
    def __call__(self, *args, **kwargs):
        self.modified__ = True
        return self._value(*args, **kwargs)
    def __iter__(self):
        self.modified__ = True
        for x in self._value:
            yield x
    def from_string_converter(self):
        return get_from_string_converter(type(self.value))
    def dont_care(self):
        try:
            return not self.modified__
        except AttributeError:
            return True
    def as_bare_value(self):
        return self._value


def dont_care(value):
    value_type = type(value)
    #print 'dont_care', value, value_type
    try:
        if value_type is types.TypeType:
            X = DontCare
        else:
            result = classes[value_type](value)
            #print "  ", result
            return result
    except KeyError:
        try:
            class X(value_type):
                @classmethod
                def __hash__(kls):
                    return hash(kls.__name__)
                def append(self, item):
                    self.modified__ = True
                    return super(X, self).append(item)
                def from_string_converter(self):
                    return get_from_string_converter(value_type)
                def dont_care(self):
                    try:
                        return not self.modified__
                    except AttributeError:
                        return True
                def as_bare_value(self):
                    return self
            X.__name__ = 'DontCareAbout_%s' % to_str(value_type)

        except TypeError:
            X = DontCare
    classes[value_type] = X
    x = X(value)
    x.dont_care__ = True
    return x

