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
import inspect
import collections

from required_config import RequiredConfig
from namespace import Namespace

from .datetime_util import datetime_from_ISO_string as datetime_converter
from .datetime_util import date_from_ISO_string as date_converter

import datetime_util


#------------------------------------------------------------------------------
def option_value_str(an_option):
    """return an instance of Option's value as a string.

    The option instance doesn't actually have to be from the Option class. All
    it requires is that the passed option instance has a ``value`` attribute.
    """
    if an_option.value is None:
        return ''
    try:
        converter = to_string_converters[type(an_option.value)]
        s = converter(an_option.value)
    except KeyError:
        if not isinstance(an_option.value, basestring):
            s = unicode(an_option.value)
        else:
            s = an_option.value
    if an_option.from_string_converter in converters_requiring_quotes:
        s = "'''%s'''" % s
    return s


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
            new_dict[key] = a_dict[key]
    return new_dict


#------------------------------------------------------------------------------
def io_converter(input_str):
    """ a conversion function for to select stdout, stderr or open a file for
    writing"""
    if type(input_str) is str:
        input_str_lower = input_str.lower()
        if input_str_lower == 'stdout':
            return sys.stdout
        if input_str_lower == 'stderr':
            return sys.stderr
        return open(input_str, "w")
    return input_str


#------------------------------------------------------------------------------
def timedelta_converter(input_str):
    """a conversion function for time deltas"""
    if isinstance(input_str, basestring):
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
        return datetime.timedelta(days=days,
                                      hours=hours,
                                      minutes=minutes,
                                      seconds=seconds)
    raise ValueError(input_str)


#------------------------------------------------------------------------------
def boolean_converter(input_str):
    """ a conversion function for boolean
    """
    return input_str.lower() in ("true", "t", "1", "y", "yes")


#------------------------------------------------------------------------------
import __builtin__
_all_named_builtins = dir(__builtin__)


def class_converter(input_str):
    """ a conversion that will import a module and class name
    """
    if not input_str:
        return None
    if '.' not in input_str and input_str in _all_named_builtins:
        return eval(input_str)
    parts = input_str.split('.')
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

#------------------------------------------------------------------------------
def automatic_class_factory(factory_name):
    """this converter will take an option that holds a class and create an
    aggregation that is a factory function for the class.
    """
    def inner_fn(input_str):
        if not input_str:
            return None
        parts = input_str.split('.')
        try:
            # first try as a complete module
            package = __import__(input_str)
        except ImportError:
            # it must be a class from a module
            if len(parts) == 1:
                # since it has only one part, it must be a class from __main__
                parts = ('__main__', input_str)
            package = __import__('.'.join(parts[:-1]), globals(), locals(), [])
        class_obj = package
        for name in parts[1:]:
            class_obj = getattr(class_obj, name)
        # we'll derive a new class from class_obj to add an aggregator that
        # will instantiate the target class.

        def create_factory(config, local_config, args):
            def factory():
                return class_obj(local_config)
            return factory

        class ClassAggregationProxy(class_obj):
            required_config = Namespace()
            required_config.add_aggregation(factory_name,
                                            create_factory)

            @classmethod
            def to_str(cls):
                return input_str

        return ClassAggregationProxy
    return inner_fn

#------------------------------------------------------------------------------
def class_instantiator(instantiated_name):
    """ a conversion that will import a class and instantiate it
    it assumes that the constructor takes a config dict as parametor to the
    constructor
    """
    def inner_fn(input_str):
        if not input_str:
            return None
        parts = input_str.split('.')
        try:
            # first try as a complete module
            package = __import__(input_str)
        except ImportError:
            # it must be a class from a module
            if len(parts) == 1:
                # since it has only one part, it must be a class from __main__
                parts = ('__main__', input_str)
            package = __import__('.'.join(parts[:-1]), globals(), locals(), [])
        class_obj = package
        for name in parts[1:]:
            class_obj = getattr(class_obj, name)
        # we'll derive a new class from class_obj to add an aggregator that
        # will instantiate the target class.

        def instantiate_class_obj(config, local_config, args):
            return class_obj(local_config)

        class InstantiatorForClass(class_obj):
            required_config = Namespace()
            required_config.add_aggregation(instantiated_name,
                                            instantiate_class_obj)

            @classmethod
            def to_str(cls):
                return input_str

        return InstantiatorForClass
    return inner_fn

#------------------------------------------------------------------------------
def classes_in_namespaces_converter(namespace_template="cls%d",
                                    class_option_name='cls'):
    """take a comma delimited  list of class names, convert each class name
    into an actual class in an option within a numbered namespace.

    parameters:
        namespace_template - a template for the names of the namespaces that
                             will contain the classes and their associated
                             required config options.
        class_option_name - the name to be used for the class option within
                            the nested namespace"""

    #--------------------------------------------------------------------------
    def class_list_converter(class_list_str):
        """This function becomes the actual converter used by configman to
        take a string and convert it into the nested sequence of Namespaces,
        one for each class in the list."""
        if isinstance(class_list_str, basestring):
            class_list =  [x.strip() for x in class_list_str.split(',')]
        elif isinstance(class_list_str, collections.Sequence):
            class_list = class_list_str
        else:
            raise TypeError('must be string or list')

        #======================================================================
        class InnerClassList(RequiredConfig):
            """This nested class is a proxy list for the classes.  It collects
            all the config requirements for the listed classes and places them
            each into their own Namespace
            """
            required_config = Namespace()
            for namespace_index, a_class in enumerate(class_list):
                namespace_name = namespace_template % namespace_index
                required_config[namespace_name] = Namespace()
                required_config[namespace_name].add_option(class_option_name,
                                                    default=a_class,
                                                    from_string_converter=
                                                        class_converter)
            @classmethod
            def to_str(cls):
                """this method takes this inner class object and turns it back
                into the original string of classnames.  This is used
                primarily as for the output of the 'help' option"""
                return ', '.join(
                    py_obj_to_str(v[class_option_name].value)
                        for k, v in cls.get_required_config().iteritems()
                        if isinstance(v, Namespace))

        return InnerClassList  # result of class_list_converter
    return class_list_converter  # result of classes_in_namespaces_converter

#------------------------------------------------------------------------------
def regex_converter(input_str):
    return re.compile(input_str)

compiled_regexp_type = type(re.compile(r'x'))

#------------------------------------------------------------------------------
from_string_converters = {
    int: int,
    float: float,
    str: str,
    unicode: unicode,
    bool: boolean_converter,
    datetime.datetime: datetime_converter,
    datetime.date: date_converter,
    datetime.timedelta: timedelta_converter,
    type: class_converter,
    types.FunctionType: class_converter,
    compiled_regexp_type: regex_converter,
}


#------------------------------------------------------------------------------
def py_obj_to_str(a_thing):
    if a_thing is None:
        return ''
    if inspect.ismodule(a_thing):
        return a_thing.__name__
    if a_thing.__module__ == '__builtin__':
        return a_thing.__name__
    if a_thing.__module__ == "__main__":
        return a_thing.__name__
    if hasattr(a_thing, 'to_str'):
        return a_thing.to_str()
    return "%s.%s" % (a_thing.__module__, a_thing.__name__)


#------------------------------------------------------------------------------
def list_to_str(a_list):
    return ', '.join(to_string_converters[type(x)](x) for x in a_list)


#------------------------------------------------------------------------------
to_string_converters = {
    int: str,
    float: str,
    str: str,
    unicode: unicode,
    list: list_to_str,
    tuple: list_to_str,
    bool: lambda x: 'True' if x else 'False',
    datetime.datetime: datetime_util.datetime_to_ISO_string,
    datetime.date: datetime_util.date_to_ISO_string,
    datetime.timedelta: datetime_util.timedelta_to_str,
    type: py_obj_to_str,
    types.ModuleType: py_obj_to_str,
    types.FunctionType: py_obj_to_str,
    compiled_regexp_type: lambda x: x.pattern,
}


#------------------------------------------------------------------------------
#converters_requiring_quotes = [eval, eval_to_regex_converter]
converters_requiring_quotes = [eval, regex_converter]
