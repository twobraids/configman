# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is configman
#
# The Initial Developer of the Original Code is
# Mozilla Foundation
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#    K Lars Lohn, lars@mozilla.com
#    Peter Bengtsson, peterbe@mozilla.com
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import sys
import re
import datetime
import types
import json
import __builtin__
import decimal

from functools import partial
from collections import OrderedDict, defaultdict


from required_config import RequiredConfig
from namespace import Namespace

from .datetime_util import datetime_from_ISO_string as datetime_converter
from .datetime_util import date_from_ISO_string as date_converter
from .config_exceptions import CannotConvertError
from .dotdict import DotDict, DotDictWithAcquisition

import datetime_util

# to be used for string representation of a converter to an actual converter
# function lookup.  Example:  "configman.converters.boolean_converter" maps to
# the actual function configman.converters.boolean_converter
from_string_converter_lookup_by_str = DotDictWithAcquisition()
to_string_converter_lookup_by_str = DotDictWithAcquisition()

#------------------------------------------------------------------------------
# Utilities Section
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
_all_named_builtins = dir(__builtin__)
_compiled_regexp_type = type(re.compile(r'x'))
_builtin_function_or_method_type = type(sum)


#------------------------------------------------------------------------------
def str_dict_keys(a_dict):
    """return a modified dict where all the keys that are anything but str get
    converted to str.
    E.g.

      >>> result = str_dict_keys({u'name': u'Peter', u'age': 99, 1: 2})
      >>> # can't compare whole dicts in doctests
      >>> result['name']
      u'Peter'
      >>> result['age']
      99
      >>> result[1]
      2

    The reason for this is that in Python <= 2.6.4 doing
    ``MyClass(**{u'name': u'Peter'})`` would raise a TypeError

    Note that only unicode types are converted to str types.
    The reason for that is you might have a class that looks like this::

        class Option(object):
            def __init__(self, foo=None, bar=None, **kwargs):
                ...

    And it's being used like this::

        Option(**{u'foo':1, u'bar':2, 3:4})

    Then you don't want to change that {3:4} part which becomes part of
    `**kwargs` inside the __init__ method.
    Using integers as parameter keys is a silly example but the point is that
    due to the python 2.6.4 bug only unicode keys are converted to str.
    """
    new_dict = {}
    for key in a_dict:
        if isinstance(key, unicode):
            new_dict[str(key)] = a_dict[key]
        else:
            new_dict[to_str(key)] = a_dict[key]
    return new_dict

#------------------------------------------------------------------------------
# got a better memoizer?  feel free to replace...
def _memoizeArgsOnly (max_cache_size=1000):
    """Python 2.4 compatible memoize decorator.
    It creates a cache that has a maximum size.  If the cache exceeds the max,
    it is thrown out and a new one made.  With such behavior, it is wise to set
    the cache just a little larger that the maximum expected need.

    Parameters:
      max_cache_size - the size to which a cache can grow

    Limitations:
      The cache works only on args, not kwargs
    """
    def wrapper (f):
        def fn (*args):
            try:
                return fn.cache[args]
            except KeyError:
                if fn.count >= max_cache_size:
                    fn.cache = {}
                    fn.count = 0
                result = f(*args)
                fn.cache[args] = result
                fn.count += 1
                return result
            except TypeError:
                return f(*args)
        fn.cache = {}
        fn.count = 0
        return fn
    return wrapper
memoize = _memoizeArgsOnly  # to allow for easy replacement of the memoize
                            # decorator used below


###############################################################################
#------------------------------------------------------------------------------
# to string Section
#     these are methods that will take some object and convert it into a string
#     representation that is human readably friendly
#------------------------------------------------------------------------------


#------------------------------------------------------------------------------
# a mapping of all the builtin types to human readable strings
_builtin_to_str = dict(
    (val, key)
    for key, val in __builtin__.__dict__.iteritems()
    if not key.startswith('__') and key is not 'None'
)


#------------------------------------------------------------------------------
# a bunch of known mappings of builtin items to strings
known_mapping_type_to_str = dict(
    (val, key) for key, val in __builtin__.__dict__.iteritems()
)


#------------------------------------------------------------------------------
#@memoize(1000)
def _arbitrary_object_to_string(a_thing):
    """take a python object of some sort, and convert it into a human readable
    string"""
    # is it None?
    if a_thing is None:
        return ''

    # is it already a string?
    if isinstance(a_thing, basestring):
        return a_thing

    # does it have a to_str function?
    try:
        return a_thing.to_str()
    except (AttributeError, KeyError):
        # nope, no to_str function
        pass

    # is it a built in?
    try:
        return known_mapping_type_to_str[a_thing]
    except KeyError:
        # nope, not a builtin
        pass

    # is it something from a loaded module?
    try:
        if a_thing.__module__ not in ('__builtin__', 'exceptions'):
            return "%s.%s" % (a_thing.__module__, a_thing.__name__)
    except AttributeError:
        # nope, not one of these
        pass

    # maybe it has a __name__ attribute?
    try:
        return a_thing.__name__
    except AttributeError:
        # nope, not one of these
        pass

    # punt and see what happens if we just cast it to string
    return str(a_thing)


#------------------------------------------------------------------------------
def sequence_to_string(a_list, delimiter=", "):
    """a dedicated function that turns a list into a comma delimited string
    of items converted.  This method will flatten nested lists."""
    return delimiter.join(to_str(x) for x in a_list)


#------------------------------------------------------------------------------
def reqex_to_str(a_compilied_regular_expression):
    return a_compilied_regular_expression.pattern


#------------------------------------------------------------------------------
def _builtin_function_or_method_type_to_str(a_builtin_thing):
    return a_builtin_thing.__name__


#------------------------------------------------------------------------------
@memoize(10000)
def get_to_string_converter(a_thing):
    try:
        converter = to_string_converters[type(a_thing)]
    except KeyError:
        try:
            converter = to_string_converters[type(a_thing.as_bare_value())]
            a_thing = a_thing.as_bare_value()
        except (AttributeError, KeyError):
            converter = _arbitrary_object_to_string
    return converter

#------------------------------------------------------------------------------
def to_str(a_thing):
    """the ultimate authority in converting a thing into a human readable
    string.  Give it anything  and you'll likely get something just fine
    from it."""
    converter = get_to_string_converter(a_thing)
    result = converter(a_thing)
    return result

#------------------------------------------------------------------------------
# a mapping of types to methods that will convert the an object of the given
# type to a string.
_to_string_converters = [
    (int, str),
    (float, str),
    (str, str),
    (unicode, unicode),
    (list, sequence_to_string),
    (tuple, sequence_to_string),
    (bool, str),
    (dict, json.dumps),
    (DotDict, json.dumps),  # TODO, must be changed
    (datetime.datetime, datetime_util.datetime_to_ISO_string),
    (datetime.date, datetime_util.date_to_ISO_string),
    (datetime.timedelta, datetime_util.timedelta_to_str),
    (type, _arbitrary_object_to_string),
    (types.ModuleType, _arbitrary_object_to_string),
    (types.FunctionType, _arbitrary_object_to_string),
    (types.BuiltinMethodType, _arbitrary_object_to_string),
    (types.BuiltinFunctionType, _arbitrary_object_to_string),
    (_builtin_function_or_method_type, lambda x: x.__name__),
    (_compiled_regexp_type, reqex_to_str),
    (type, _arbitrary_object_to_string)
]

to_string_converters = OrderedDict()

for key, value in _to_string_converters:
    to_string_converters[key] = value
    to_string_converter_lookup_by_str[to_str(key)] = value


# for reverse lookup, see the end of the file after the from_string section

###############################################################################
#------------------------------------------------------------------------------
# from string Section
#     these are methods that will take a string and convert it into an instance
#     of some type.
#------------------------------------------------------------------------------


#------------------------------------------------------------------------------
def io_converter(input_str):
    """ a conversion function for to select stdout, stderr or open a file for
    writing"""
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    input_str_lower = input_str.lower()
    if input_str_lower == 'stdout':
        return sys.stdout
    if input_str_lower == 'stderr':
        return sys.stderr
    return open(input_str, "w")
from_string_converter_lookup_by_str[to_str(io_converter)] = io_converter


#------------------------------------------------------------------------------
def timedelta_converter(input_str):
    """a conversion function for time deltas"""
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    days, hours, minutes, seconds = 0, 0, 0, 0
    details = input_str.split(':')
    if len(details) >= 4:
        days = int(details[-4])
    if len(details) >= 3:
        hours = int(details[-3])
    if len(details) >= 2:
        minutes = int(details[-2])
    if len(details) >= 1:
        seconds = int(details[-1])
    return datetime.timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )
from_string_converter_lookup_by_str[
    to_str(timedelta_converter)
] = timedelta_converter


#------------------------------------------------------------------------------
def boolean_converter(input_str):
    """ a conversion function for boolean
    """
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    return input_str.lower() in ("true", "t", "1", "y", "yes")
from_string_converter_lookup_by_str[
    to_str(boolean_converter)
] = boolean_converter


#------------------------------------------------------------------------------
def list_converter(input_str, item_converter=to_str, item_separator=',',
                   list_to_collection_converter=None):
    """ a conversion function for list
    """
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    result = [
        item_converter(x.strip())
        for x in input_str.split(item_separator) if x.strip()
    ]
    if list_to_collection_converter is not None:
        return list_to_collection_converter(result)
    return result
from_string_converter_lookup_by_str[to_str(list_converter)] = list_converter

#------------------------------------------------------------------------------
list_space_separated_strings = partial(list_converter, item_separator=' ')
from_string_converter_lookup_by_str[to_str(list_space_separated_strings)] = \
    list_space_separated_strings

#------------------------------------------------------------------------------
list_comma_separated_ints = partial(list_converter, item_converter=int)
from_string_converter_lookup_by_str[to_str(list_comma_separated_ints)] = \
    list_comma_separated_ints

#------------------------------------------------------------------------------
list_space_separated_ints = partial(
    list_converter,
    item_converter=int,
    item_separator=',',
)
from_string_converter_lookup_by_str[to_str(list_space_separated_ints)] = \
    list_space_separated_ints

#------------------------------------------------------------------------------
import __builtin__
_all_named_builtins = dir(__builtin__)


#------------------------------------------------------------------------------
@memoize(10000)
def class_converter(input_str):
    """ a conversion that will import a module and class name
    """
    if not input_str:
        return None
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    if '.' not in input_str and input_str in _all_named_builtins:
        return eval(input_str)
    parts = [x.strip() for x in input_str.split('.') if x.strip()]
    try:
        try:
            # first try as a complete module
            package = __import__(input_str)
        except ImportError:
            # it must be a class from a module
            if len(parts) == 1:
                # since it has only one part, it must be a class from __main__
                parts = ('__main__', input_str)
            package = __import__('.'.join(parts[:-1]), globals(), locals(), [])
        obj = package
        for name in parts[1:]:
            obj = getattr(obj, name)
        return obj
    except AttributeError, x:
        raise CannotConvertError("%s cannot be found" % input_str)
    except ImportError, x:
        raise CannotConvertError(str(x))
from_string_converter_lookup_by_str[to_str(class_converter)] = class_converter


#------------------------------------------------------------------------------
def classes_in_namespaces_converter(
    template_for_namespace="cls%d",
    name_of_class_option='cls',
    instantiate_classes=False
):
    """take a comma delimited  list of class names, convert each class name
    into an actual class as an option within a numbered namespace.  This
    function creates a closure over a new function.  That new function,
    in turn creates a class derived from RequiredConfig.  The inner function,
    'class_list_converter', populates the InnerClassList with a Namespace for
    each of the classes in the class list.  In addition, it puts the each class
    itself into the subordinate Namespace.  The requirement discovery mechanism
    of configman then reads the InnerClassList's requried config, pulling in
    the namespaces and associated classes within.

    For example, if we have a class list like this: "Alpha, Beta", then this
    converter will add the following Namespaces and options to the
    configuration:

        "cls0" - the subordinate Namespace for Alpha
        "cls0.cls" - the option containing the class Alpha itself
        "cls1" - the subordinate Namespace for Beta
        "cls1.cls" - the option containing the class Beta itself

    Optionally, the 'class_list_converter' inner function can embue the
    InnerClassList's subordinate namespaces with aggregates that will
    instantiate classes from the class list.  This is a convenience to the
    programmer who would otherwise have to know ahead of time what the
    namespace names were so that the classes could be instantiated within the
    context of the correct namespace.  Remember the user could completely
    change the list of classes at run time, so prediction could be difficult.

        "cls0" - the subordinate Namespace for Alpha
        "cls0.cls" - the option containing the class Alpha itself
        "cls0.cls_instance" - an instance of the class Alpha
        "cls1" - the subordinate Namespace for Beta
        "cls1.cls" - the option containing the class Beta itself
        "cls1.cls_instance" - an instance of the class Beta

    parameters:
        template_for_namespace - a template for the names of the namespaces
                                 that will contain the classes and their
                                 associated required config options.  The
                                 namespaces will be numbered sequentially.  By
                                 default, they will be "cls1", "cls2", etc.
        class_option_name - the name to be used for the class option within
                            the nested namespace.  By default, it will choose:
                            "cls1.cls", "cls2.cls", etc.
        instantiate_classes - a boolean to determine if there should be an
                              aggregator added to each namespace that
                              instantiates each class.  If True, then each
                              Namespace will contain elements for the class, as
                              well as an aggregator that will instantiate the
                              class.
                              """

    #--------------------------------------------------------------------------
    def class_list_converter(class_list_str):
        """This function becomes the actual converter used by configman to
        take a string and convert it into the nested sequence of Namespaces,
        one for each class in the list.  It does this by creating a proxy
        class stuffed with its own 'required_config' that's dynamically
        generated."""
        if isinstance(class_list_str, basestring):
            class_list = [x.strip() for x in class_list_str.split(',')]
            if class_list == ['']:
                class_list = []
        else:
            raise TypeError('must be derivative of a basestring')

        #======================================================================
        class InnerClassList(RequiredConfig):
            """This nested class is a proxy list for the classes.  It collects
            all the config requirements for the listed classes and places them
            each into their own Namespace.
            """
            # we're dynamically creating a class here.  The following block of
            # code is actually adding class level attributes to this new class
            required_config = Namespace()  # 1st requirement for configman
            subordinate_namespace_names = []  # to help the programmer know
                                              # what Namespaces we added
            namespace_template = template_for_namespace  # save the template
                                                         # for future reference
            class_option_name = name_of_class_option  # save the class's option
                                                      # name for the future
            original_class_list_str = class_list_str
            # for each class in the class list
            for namespace_index, a_class in enumerate(class_list):
                # figure out the Namespace name
                namespace_name = template_for_namespace % namespace_index
                subordinate_namespace_names.append(namespace_name)
                # create the new Namespace
                required_config[namespace_name] = Namespace()
                # add the option for the class itself
                required_config[namespace_name].add_option(
                    name_of_class_option,
                    #doc=a_class.__doc__  # not helpful if too verbose
                    default=a_class,
                    from_string_converter=class_converter
                )
                if instantiate_classes:
                    # add an aggregator to instantiate the class
                    required_config[namespace_name].add_aggregation(
                        "%s_instance" % name_of_class_option,
                        lambda c, lc, a: lc[name_of_class_option](lc)
                    )

            @classmethod
            def to_str(cls):
                """this method takes this inner class object and turns it back
                into the original string of classnames.  This is used
                primarily as for the output of the 'help' option"""
                return cls.original_class_list_str

        return InnerClassList  # result of class_list_converter
    return class_list_converter  # result of classes_in_namespaces_converter
from_string_converter_lookup_by_str[
    to_str(classes_in_namespaces_converter)
] = classes_in_namespaces_converter


#------------------------------------------------------------------------------
def regex_converter(input_str):
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    return re.compile(input_str)
from_string_converter_lookup_by_str[to_str(regex_converter)] = regex_converter


#------------------------------------------------------------------------------
def str_quote_stripper(input_str):
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    while (
        input_str
        and input_str[0] == input_str[-1]
        and input_str[0] in ("'", '"')
    ):
        input_str = input_str.strip(input_str[0])
    return input_str
from_string_converter_lookup_by_str[
    to_str(str_quote_stripper)
] = str_quote_stripper

#------------------------------------------------------------------------------
# a mapping of some types to converter methods to assist in finding the right
# conversion automatically

#------------------------------------------------------------------------------
_associations = [
    (long, long),
    (float, float),
    (int, int),
    (bool, boolean_converter),
    (unicode, str_quote_stripper),
    (str, str_quote_stripper),
    (dict, json.loads),
    (list, list_converter),
    (datetime.datetime, datetime_converter),
    (datetime.date, date_converter),
    (datetime.timedelta, timedelta_converter),
    (decimal.Decimal, decimal.Decimal),
    (types.FunctionType, class_converter),
    (_compiled_regexp_type, regex_converter),
    (_builtin_function_or_method_type, class_converter),
]

from_string_converters = OrderedDict()

for key, value in _associations:
    from_string_converters[key] = value
    from_string_converter_lookup_by_str[to_str(key)] = value
from_string_converters[type] = class_converter
from_string_converter_lookup_by_str[to_str(type)] = class_converter


#------------------------------------------------------------------------------
#@memoize(10000)
def get_from_string_converter(thing):
    try:
        return thing.from_string_converter
    except AttributeError:
        # no converter, move on
        pass
    # try exact type match first
    try:
        if isinstance(thing, type):
            return from_string_converters[thing]
        return from_string_converters[type(thing)]
    except KeyError:
        # not found with exact match
        pass
    # look for an "isinstance" relationship
    for key, value in from_string_converters.iteritems():
        if thing is key or isinstance(thing, key):
            return value
    return None


# other stuff
#------------------------------------------------------------------------------
# in an Option, the from_string_converter may have required that a string have
# quotes.  This is a list of those converters for the benefit of the Option
# class when it wants to convert _to_ a string.  It helps to make sure that
# the from/to conversion can survive a round trip
converters_requiring_quotes = [eval, regex_converter]

#------------------------------------------------------------------------------
#  reverse lookup for to string converters from from string converters
_to_string_converters_indexed_by_from_string_converters = [
    (long, str),
    (float, str),
    (int, str),
    (bool, str),
    (unicode, str),
    (str, str),
    (dict, json.dumps),
    (list, sequence_to_string),
    (tuple, sequence_to_string),
    (boolean_converter, str),
    (datetime_converter, datetime_util.datetime_to_ISO_string),
    (date_converter, datetime_util.date_to_ISO_string),
    (timedelta_converter, datetime_util.timedelta_to_str),
    (decimal.Decimal, str),
    (class_converter, _arbitrary_object_to_string),
    (regex_converter, reqex_to_str),
]

to_string_converters_by_from_string_converters = {}

for key, value in _to_string_converters_indexed_by_from_string_converters:
    to_string_converters_by_from_string_converters[key] = value


#------------------------------------------------------------------------------
def get_to_string_converter_by_reverse_lookup(a_from_string_converter):
    try:
        return to_string_converters_by_from_string_converters[
            a_from_string_converter
        ]
    except KeyError:
        return None


