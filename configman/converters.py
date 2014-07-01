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
import json
import __builtin__
import decimal

from functools import partial
from collections import OrderedDict, defaultdict, Sequence

from required_config import RequiredConfig
from namespace import Namespace

from .datetime_util import datetime_from_ISO_string as datetime_converter
from .datetime_util import date_from_ISO_string as date_converter
from .config_exceptions import CannotConvertError
from .dotdict import DotDict, DotDictWithAcquisition

import datetime_util

from configman.config_exceptions import CannotConvertError

#------------------------------------------------------------------------------
# Utilities Section
#------------------------------------------------------------------------------

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
        elif isinstance(key, basestring):
            new_dict[key] = a_dict[key]
        else:
            new_dict[str(key)] = a_dict[key]
    return new_dict

#------------------------------------------------------------------------------
_compiled_regexp_type = type(re.compile(r'x'))


#------------------------------------------------------------------------------
def last_repeat_generator(iterable):
    for x in iterable:
        yield x
    while True:
        yield x

#------------------------------------------------------------------------------
def memoize (max_cache_size=1000, arg_type_index=0):
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
            # Python says True == 1, therefore if we cache based on value alone
            # for the cases of True and 1, then we have ambiguity.  This is a
            # hack to differentiate them based on type for the cache.
            key = (args, type(args[arg_type_index]))
            try:
                result = fn.cache[key]
                return fn.cache[key]
            except KeyError:
                if fn.count >= max_cache_size:
                    fn.cache = {}
                    fn.count = 0
                result = f(*args)
                fn.cache[key] = result
                fn.count += 1
                return result
            except TypeError:
                return f(*args)
        fn.cache = {}
        fn.count = 0
        return fn
    return wrapper
memoize_instance_method = partial(memoize, arg_type_index=1)

#------------------------------------------------------------------------------
# a bunch of known mappings of builtin items to strings
known_mapping_type_to_str = dict(
    (val, key) for key, val in __builtin__.__dict__.iteritems()
    if val not in (True, False)
)
known_mapping_str_to_type = dict(
    (key, val) for key, val in __builtin__.__dict__.iteritems()
    if val not in (True, False)
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
    except (AttributeError, KeyError, TypeError), x:
        # nope, no to_str function
        pass
    # is this a type proxy?
    try:
        return _arbitrary_object_to_string(a_thing.a_type)
    except (AttributeError, KeyError, TypeError), x:
        # nope, no a_type property
        pass
    # is it a built in?
    try:
        return known_mapping_type_to_str[a_thing]
    except (KeyError, TypeError):
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


#==============================================================================
class AnyInstanceOf(object):
    def __init__(self, a_thing):
        if isinstance(a_thing, type):
            a_type = a_thing
        else:
            a_type = type(a_thing)
        self.a_type = a_type


#==============================================================================
class ConverterElement(object):
    def __init__(
        self,
        subject,
        converter_function,
        objective_type=str
    ):
        self.subject = subject
        self.subject_key = _arbitrary_object_to_string(subject)

        self.objective_type = objective_type
        self.objective_type_key = _arbitrary_object_to_string(objective_type)

        self.converter_function = converter_function
        self.converter_function_key = _arbitrary_object_to_string(
            converter_function
        )

    #--------------------------------------------------------------------------
    #@memoize_instance_method(1000)
    def __call__(self, a_value):
        try:
            converted_value = self.converter_function(a_value)
            #if self.objective_type is str:
                #return value_as_string
            #else:
                #final = self.objective_type(value_as_string)
                #return final
            return converted_value
        except (TypeError, ValueError), x:
            CannotConvertError(
                'Converting %s to %s failed: %s' %
                (self.subject_key, self.objective_type_key, x)
            )


#==============================================================================
class ConverterService(object):
    #--------------------------------------------------------------------------
    def __init__(self):
        self.by_subject_and_objective = {}  # keyed by tuple(
                                            # subject_key,
                                            # objective_type_key)
        # does this one need the 'subject' too?
        self.by_function_and_objective = {}  # keyed by tuple(
                                             #converter_function_key,
                                             # objective_type_key)
        self.by_instance_of_subject_and_objective = {}  # keyed by tuple(
                                                        # subject_key,
                                                        # objective_type_key
        self.no_match_library = {}  # keyed by objective_type_key for use when all
                                    # else fails

    #--------------------------------------------------------------------------
    def register_converter(
        self,
        subject,
        converter_function,
        objective_type=str,
        force = False  # overwrite is ok
    ):
        if isinstance(subject, AnyInstanceOf):
            a_converter_element = ConverterElement(
                subject.a_type,
                converter_function,
                objective_type
            )
            key = (
                a_converter_element.subject_key,
                a_converter_element.objective_type_key,
            )
            if key not in self.by_instance_of_subject_and_objective or force:
                self.by_instance_of_subject_and_objective[key] = \
                    a_converter_element
        else:
            a_converter_element = ConverterElement(
                subject,
                converter_function,
                objective_type
            )
            key = (
                a_converter_element.subject_key,
                a_converter_element.objective_type_key,
            )
            if key not in self.by_subject_and_objective or force:
                self.by_subject_and_objective[key] = a_converter_element
                self.by_function_and_objective[(
                    a_converter_element.converter_function_key,
                    a_converter_element.objective_type_key,
                )] = a_converter_element


    #--------------------------------------------------------------------------
    def register_no_match_converter(self, objective_type, converter_function):
        a_converter_element = ConverterElement(
            None,
            converter_function,
            objective_type
        )
        self.no_match_library[objective_type] = a_converter_element

    #--------------------------------------------------------------------------
    @staticmethod
    def lookup_without_keyerror(mapping, key):
        try:
            return mapping[key]
        except KeyError:
            return None

    #--------------------------------------------------------------------------
    def converter_search_generator(
        self,
        the_subject,
        objective_type_key,
        converter_function_key,
    ):
        if converter_function_key is not None:
            # here's where we get the abilty to find and existing converter
            # and override it with a new something different.  Local for_*
            # handlers may require their own converters for local types.  An
            # option may have a converter assigned that needs to be overridden
            result =  self.lookup_without_keyerror(
                self.by_function_and_objective,
                (converter_function_key, objective_type_key),
            )
            if result is not None:
                yield Result

        # either we're not looking to override any converter by
        # converter_function_key or we failed in trying to do so.  Go on with
        # search for an appropriate converter.
        # is there a converter for an instance of the type of the subject?
        if isinstance(the_subject, AnyInstanceOf):
            the_subject_type = the_subject.a_type
        #elif isinstance(the_subject, type):
            #the_subject_type = type(the_subject)
        else:
            the_subject_type = type(the_subject)
        subject_type_key = _arbitrary_object_to_string(the_subject_type)
        result =  self.lookup_without_keyerror(
            self.by_instance_of_subject_and_objective,
            (subject_type_key, objective_type_key)
        )
        if result is not None:
            yield result

        # if execution has gotten here, then the previous search was
        # unsuccessful of unacceptable.  Let's look for a direct converter
        # for the subject itself, instead of the subject's type.
        subject_key = _arbitrary_object_to_string(the_subject)
        result = self.lookup_without_keyerror(
            self.by_subject_and_objective,
            (subject_key, objective_type_key)
        )
        if result is not None:
            yield result

        # the previous search failed or the result was unacceptable.  All
        # we have left is a fallback based on the target objective type.
        result = self.lookup_without_keyerror(
            self.no_match_library,
            objective_type_key
        )
        if result is not None:
            yield result

        # getting here in the exectution means that we failed in every
        # attempt to find a converter.  Let the iterator quit and the
        # caller will just have to deal with failure.

    #--------------------------------------------------------------------------
    #@memoize_instance_method(1000)
    def convert(
        self,
        a_thing,
        objective_type_key='str',
        converter_function_key=None,  # used to lookup a
    ):
        for converter_element in self.converter_search_generator(
            a_thing, objective_type_key, converter_function_key
        ):
            try:
                converted_thing = converter_element(a_thing)
                return converted_thing
            except TypeError:
                # likely "None not callable"
                pass
            except Exception, x:
                raise CannotConvertError(
                    "Error in conversion for '%s' to '%s': %s" % (
                        _arbitrary_object_to_string(a_thing),
                        objective_type_key,
                        x
                    )
                )
        raise CannotConvertError(
            "There is no converter for '%s' to '%s'" % (
                _arbitrary_object_to_string(a_thing),
                objective_type_key
            )
        )

    #--------------------------------------------------------------------------
    #@memoize_instance_method(1000)
    def get_converter(
        self,
        a_thing,
        objective_type_key='str',
        converter_function_key=None,  # used to lookup a
    ):
        result = self.get_converter_element(
            a_thing,
            objective_type_key,
            converter_function_key
        )
        if result is not None:
            return result.converter_function
        return None

    #--------------------------------------------------------------------------
    #@memoize_instance_method(1000)
    def get_converter_element(
        self,
        a_thing,
        objective_type_key='str',
        converter_function_key=None,  # used to lookup a
    ):
        for converter_element in self.converter_search_generator(
            a_thing, objective_type_key, converter_function_key
        ):
            if converter_element is None:
                continue
            return converter_element
        return None


    #--------------------------------------------------------------------------
    #@memoize_instance_method(1000)
    def get_converter_by_reverse(
        self,
        a_thing,
        objective_type_key='str',
        reverse_converter_function_key=None,  # used to lookup a
    ):
        for converter_element in self.converter_search_generator(
            a_thing, converter_function_key, objective_type_key
        ):
            try:
                if converter_element is None:
                    continue
                return converter_element.converter_function
            except TypeError:
                # likely "None not callable"
                pass
            except Exception, x:
                raise CannotConvertError(
                    "There is no converter for '%s' to '%s'" % (
                        _arbitrary_object_to_string(a_thing),
                        objective_type_key
                    )
                )
        return None


#==============================================================================
#class ConverterLibrary(object):
    #def __init__(self)

converter_service = ConverterService()
#------------------------------------------------------------------------------
def to_str(a_thing):
    return converter_service.convert(a_thing, 'str')

#------------------------------------------------------------------------------
# register built in converters
#------------------------------------------------------------------------------
#def make_identity_converter(key):
    #def identitiy_converter(x):
        #return key
    #return identitiy_converter

##------------------------------------------------------------------------------
#for key, value in __builtin__.__dict__.iteritems():
    #if key == 'bytes':
        #key = 'str'
    #if key is '__package__' and value is None:
        #key = ''
    #if key is 'type':  # wo don't want to confuse converting types to strings
        #continue
    #converter_service.register_converter(
        #value,
        #make_identity_converter(key),
        #str
    #)
    #converter_service.register_converter(
        #key,
        #make_identity_converter(value),
        #value
    #)

#------------------------------------------------------------------------------
#import types
#for key, value in types.__dict__.iteritems():
    #converter_service.register_converter(
        #value,
        #make_identity_converter(key),
        #str
    #)
    #converter_service.register_converter(
        #key,
        #make_identity_converter(value),
        #value
    #)

#------------------------------------------------------------------------------
# add known converters
converter_service.register_converter(bool, _arbitrary_object_to_string, str)
converter_service.register_converter(
    AnyInstanceOf(type),
    _arbitrary_object_to_string,
    str
)
converter_service.register_converter(AnyInstanceOf(str), int, int)
converter_service.register_converter(AnyInstanceOf(str), float, float)
converter_service.register_converter(AnyInstanceOf(str), long, long)
converter_service.register_converter(
    AnyInstanceOf(str),
    decimal.Decimal,
    decimal.Decimal
)

#------------------------------------------------------------------------------
converter_service.register_no_match_converter(
    'str',
    _arbitrary_object_to_string
)
#------------------------------------------------------------------------------
# specialty converters
#------------------------------------------------------------------------------
def sequence_to_string(a_list, delimiter=", "):
    """a dedicated function that turns a list into a comma delimited string
    of items converted.  This method will flatten nested lists."""
    return delimiter.join(to_str(x) for x in a_list)
converter_service.register_converter(
    AnyInstanceOf(list),
    sequence_to_string,
    objective_type=str
)
converter_service.register_converter(
    AnyInstanceOf(tuple),
    sequence_to_string,
    objective_type=str
)

#------------------------------------------------------------------------------
converter_service.register_converter(
    AnyInstanceOf(dict),
    json.dumps,
    objective_type=str
)
converter_service.register_converter(
    AnyInstanceOf(str),
    json.loads,
    objective_type=dict
)


#------------------------------------------------------------------------------
def reqex_to_str(a_compilied_regular_expression):
    return a_compilied_regular_expression.pattern
converter_service.register_converter(
    AnyInstanceOf(_compiled_regexp_type),
    reqex_to_str,
    objective_type=str
)

#------------------------------------------------------------------------------
converter_service.register_converter(
    AnyInstanceOf(datetime.datetime),
    datetime_util.datetime_to_ISO_string,
    objective_type=str
)
converter_service.register_converter(
    AnyInstanceOf(datetime.date),
    datetime_util.date_to_ISO_string,
    objective_type=str
)
converter_service.register_converter(
    AnyInstanceOf(datetime.timedelta),
    datetime_util.timedelta_to_str,
    objective_type=str
)


#------------------------------------------------------------------------------
def timedelta_converter(input_str):
    """a conversion function for time deltas"""
    # print '1 timedelta_converter with', input_str, type(input_str)
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    # print '2 timedelta_converter with', input_str, type(input_str)
    input_str = str_quote_stripper(input_str)
    days, hours, minutes, seconds = 0, 0, 0, 0
    details = input_str.split(':')
    # print '3 timedelta_converter with', input_str, type(input_str)
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
converter_service.register_converter(
    AnyInstanceOf(str),
    timedelta_converter,
    objective_type=datetime.timedelta
)

#------------------------------------------------------------------------------
converter_service.register_converter(
    AnyInstanceOf(str),
    datetime_converter,
    objective_type=datetime.datetime
)
converter_service.register_converter(
    AnyInstanceOf(str),
    date_converter,
    objective_type=datetime.date
)

#------------------------------------------------------------------------------
def boolean_converter(input_str):
    """ a conversion function for boolean
    """
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    return input_str.lower() in ("true", "t", "1", "y", "yes")
converter_service.register_converter(
    AnyInstanceOf(str),
    boolean_converter,
    objective_type=bool
)


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
converter_service.register_converter(
    AnyInstanceOf(str),
    list_converter,
    objective_type=list
)
list_space_separated_strings = partial(list_converter, item_separator=' ')
# not registered, for_* handlers may wish to register if needed
#converter_service.register_converter(
    #AnyInstanceOf(str),
    #list_space_separated_strings,
    #objective_type=list
#)

list_comma_separated_ints = partial(list_converter, item_converter=int)
# not registered, for_* handlers may wish to register if needed
#converter_service.register_converter(
    #AnyInstanceOf(str),
    #list_comma_separated_ints,
    #objective_type=list
#)
list_space_separated_ints = partial(
    list_converter,
    item_converter=int,
    item_separator=',',
)
# not registered, for_* handlers may wish to register if needed
#converter_service.register_converter(
    #AnyInstanceOf(str),
    #list_space_separated_ints,
    #objective_type=list
#)

#------------------------------------------------------------------------------
#@memoize(10000)
def class_converter(input_str):
    """ a conversion that will import a module and class name
    """
    if not input_str:
        return None
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    if '.' not in input_str and input_str in known_mapping_str_to_type:
        return known_mapping_str_to_type[input_str]
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
converter_service.register_converter(
    AnyInstanceOf(str),
    class_converter,
    objective_type=object
)


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
converter_service.register_converter(
    AnyInstanceOf(str),
    classes_in_namespaces_converter,
    objective_type=list
)

#------------------------------------------------------------------------------
def regex_converter(input_str):
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    return re.compile(input_str)
converter_service.register_converter(
    AnyInstanceOf(str),
    regex_converter,
    objective_type=_compiled_regexp_type
)


#------------------------------------------------------------------------------
def utf8_converter(input_str):
    if not isinstance(input_str, basestring):
        raise ValueError(input_str)
    input_str = str_quote_stripper(input_str)
    return unicode(input_str, "utf-8")
converter_service.register_converter(
    AnyInstanceOf(str),
    utf8_converter,
    objective_type=unicode
)

#------------------------------------------------------------------------------
def unicode_to_str(input_unicode):
    if not isinstance(input_unicode, unicode):
        raise ValueError(input_unicode)
    input_unicode = str_quote_stripper(input_unicode)
    return input_unicode.encode('utf8')
converter_service.register_converter(
    AnyInstanceOf(unicode),
    unicode_to_str,
    objective_type=str
)

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
converter_service.register_converter(
    AnyInstanceOf(unicode),
    str_quote_stripper,
    objective_type=unicode
)
converter_service.register_converter(
    AnyInstanceOf(str),
    str_quote_stripper,
    objective_type=str
)


#------------------------------------------------------------------------------
def get_from_string_converter(objective_type):
    """given a type, find a converter that will take a string representation
    and convert it into that type.

    It is NOT appropriate for pass in instances of the target type, we need a
    type itself.
        get_from_string_converter(int)  # yes
        get_from_string_converter(100)  # no
    """
    if not isinstance(objective_type, type):
        # an instance has been passed in rather than a type, get the type
        # and continue
        objective_type=type(objective_type)
    objective_type_key = _arbitrary_object_to_string(objective_type)
    return converter_service.get_converter(
        AnyInstanceOf(str),
        objective_type_key
    )

#------------------------------------------------------------------------------
def get_to_string_converter(subject_type):
    """given a type, find a converter that will take an instance of that type
    and convert it into a string.

    It is NOT appropriate for pass in instances of the target type, we need a
    type itself.
        get_to_string_converter(int)  # yes
        get_to_string_converter(100)  # no
    """
    assert isinstance(subject_type, type)
    return converter_service.get_converter_element(
        AnyInstanceOf(subject_type),
        'str'
    )

#------------------------------------------------------------------------------
def to_str(a_thing):
    """given an instance of something, convert it into a string"""
    return converter_service.convert(a_thing, 'str')



cv = converter_service.get_converter_element(
    AnyInstanceOf(str),
    'str'
)
print cv
print cv.subject, cv.subject_key
print cv.objective_type, cv.objective_type_key
print cv.converter_function, cv.converter_function_key
print "****", get_from_string_converter(str)
#assert(cv is str)

cv = converter_service.get_converter_element(
    AnyInstanceOf(type),
    'str'
)
print cv
print cv.subject, cv.subject_key
print cv.objective_type, cv.objective_type_key
print cv.converter_function, cv.converter_function_key
#assert(cv is str)

print "an instance of type, taking type str and converting to str"
print "result:", cv.converter_function(str)
print "converter_service.convert:", converter_service.convert(str)
print "to_str:", to_str(bool)

print "result:", cv.converter_function(unicode)

d = datetime.datetime.now()
print 'datetime'
print "an instance of type, taking type d and converting to d"
print "result:", converter_service.get_converter(d)
print "converter_service.convert:", converter_service.get_converter_element(d).converter_function
print "to_str:", to_str(d)



