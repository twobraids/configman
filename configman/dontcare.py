from configman.converters import to_str

classes = {}

class DontCare(object):
    def __init__(self, value):
        self._value = value
    def __str__(self):
        return to_str(self._value)

def dont_care(value):
    value_type = type(value)
    try:
        return classes[value_type](value)
    except KeyError:
        try:
            class X(value_type):
                @classmethod
                def __hash__(kls):
                    return hash(kls.__name__)
            X.__name__ = 'DontCareAbout_%s' % to_str(value_type)
        except TypeError:
            X = DontCare
        classes[value_type] = X
        return X(value)

