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

import types
import sys
import datetime
import json

from inspect import isclass, ismodule, isfunction
from types import NoneType

from configman.namespace import Namespace
from configman.dotdict import DotDict
from configman.option import Option
from configman.converters import (
    to_str,
    class_converter,
    known_mapping_str_to_type,
    CannotConvertError,
    str_quote_stripper,
)
file_name_extension = 'py'


can_handle = (
    types.ModuleType,
    basestring
)

#------------------------------------------------------------------------------
# Converter Section
#------------------------------------------------------------------------------

# each value source is allowed to have its own set of converters for
# serializing objects to strings.  This converter section defines the functions
# that can serialize objects into Python code.  This allows writing of a
# Python module in the same manner that ini files are written.


#------------------------------------------------------------------------------
def sequence_to_string(
    a_list,
    open_bracket_char='[',
    close_bracket_char=']',
    delimiter=", "
):
    """a dedicated function that turns a list into a comma delimited string
    of items converted.  This method will flatten nested lists."""
    return "%s%s%s" % (
        open_bracket_char,
        delimiter.join(
            local_to_str(x)
            for x in a_list
        ),
        close_bracket_char
    )


#------------------------------------------------------------------------------
def dict_to_string(d):
    return '\n'.join(
        x.rstrip() for x in json.dumps(
            d,
            indent=4,
            sort_keys=True
        ).splitlines()
    )


#------------------------------------------------------------------------------
def string_to_string(a_string):
    quote = '"'
    if '"' in a_string:
        quote = "'"
    if "'" in a_string:
        quote = '"""'
    if "/n" in a_string:
        quote = "'''"
    return "%s%s%s" % (quote, a_string, quote)


#------------------------------------------------------------------------------
def unicode_to_unicode(a_string):
    quote = '"'
    if '"' in a_string:
        quote = "'"
    if "'" in a_string:
        quote = '"""'
    if "/n" in a_string:
        quote = "'''"
    return "u%s%s%s" % (quote, a_string, quote)


#------------------------------------------------------------------------------
def datetime_to_string(d):
    return "datetime(year=%s, month=%s, day=%s, hour=%s, " \
        "minute=%s, second=%s)" % (
            d.year,
            d.month,
            d.day,
            d.hour,
            d.minute,
            d.second,
        )


#------------------------------------------------------------------------------
def date_to_string(d):
    return "date(year=%s, month=%s, day=%s)" % (
        d.year,
        d.month,
        d.day,
    )


#------------------------------------------------------------------------------
def timedelta_to_string(d):
    return "timedelta(days=%s, seconds=%s)" % (
        d.days,
        d.seconds,
    )


#------------------------------------------------------------------------------
def get_import_for_type(t):
    t_as_string = to_str(t)
    if '.' in t_as_string:
        parts = t_as_string.split('.')
        return "from %s import %s" % ('.'.join(parts[:-1]), parts[-1])
    else:
        if t_as_string in known_mapping_str_to_type:
            return None
        return 'import %s' % t_as_string


#------------------------------------------------------------------------------
local_to_string_converters = {
    str: string_to_string,
    unicode: unicode_to_unicode,
    list: sequence_to_string,
    tuple: sequence_to_string,
    dict: dict_to_string,
    datetime.datetime: datetime_to_string,
    datetime.date: date_to_string,
    datetime.timedelta: timedelta_to_string,
    NoneType: lambda x: "None"
}


#------------------------------------------------------------------------------
def find_to_string_converter(a_thing):
    for a_candidate_type, to_string_converter in local_to_string_converters:
        if isinstance(a_thing, a_candidate_type):
            return to_string_converter
    return None


#------------------------------------------------------------------------------
def local_to_str(a_thing):
    try:
        return local_to_string_converters[type(a_thing)](a_thing)
    except KeyError:
        try:
            return find_to_string_converter(a_thing)(a_thing)
        except TypeError:
            return to_str(a_thing)


#==============================================================================
class ValueSource(object):
    #--------------------------------------------------------------------------
    def __init__(self, source, the_config_manager=None):
        if isinstance(source, basestring):
            source = class_converter(source)
        module_as_dotdict = DotDict()
        try:
            ignore_symbol_list = source.ignore_symbol_list
            if 'ignore_symbol_list' not in ignore_symbol_list:
                ignore_symbol_list.append('ignore_symbol_list')
        except AttributeError:
            ignore_symbol_list = []
        try:
            self.always_ignore_mismatches = source.always_ignore_mismatches
        except AttributeError:
            pass  # don't need to do anything - mismatches will not be ignored
        for key, value in source.__dict__.iteritems():
            if key.startswith('__') and key != "__doc__":
                continue
            if key in ignore_symbol_list:
                continue
            module_as_dotdict[key] = value
        self.module = source
        self.source = module_as_dotdict

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches, obj_hook=DotDict):
        if isinstance(self.source, obj_hook):
            return self.source
        return obj_hook(initializer=self.source)

    #--------------------------------------------------------------------------
    @staticmethod
    def write_class(key, value, output_stream):
        class_str = local_to_str(value)
        parts = [x.strip() for x in class_str.split('.') if x.strip()]
        print >>output_stream, '%s = %s' % (key, parts[-1])

    #--------------------------------------------------------------------------
    @staticmethod
    def write_bare_value(key, value, output_stream):
        if isclass(value):
            ValueSource.write_class(key, value, output_stream)
            return
        try:
            value = local_to_str(value)
        except CannotConvertError:
            value = repr(value)
        if '\n' in value:
            value = "'''%s'''" % str_quote_stripper(value)
        print >>output_stream, '%s = %s' % (key, value)

    #--------------------------------------------------------------------------
    @staticmethod
    def write_option(key, an_option, output_stream):
        print >>output_stream, '\n',
        if an_option.doc:
            print >>output_stream, '# %s' % an_option.doc
        if (
            isclass(an_option.value)
            or ismodule(an_option.value)
            or isfunction(an_option.value)
        ):
            ValueSource.write_class(key, an_option.value, output_stream)
            return
        else:
            value = local_to_str(an_option.value)
            print >>output_stream, '%s = %s' % (key, value)

    #--------------------------------------------------------------------------
    @staticmethod
    def write_namespace(key, a_namespace, output_stream):
        print >>output_stream, '\n# Namespace:', key
        if hasattr(a_namespace, 'doc'):
            print >>output_stream, '#', a_namespace.doc
        print >>output_stream, '%s = DotDict()' % key

    #--------------------------------------------------------------------------
    @staticmethod
    def write(source_mapping, output_stream=sys.stdout):
        imports = set()
        # look ahead to see what sort of imports we're going to have to do
        for key in source_mapping.keys_breadth_first():
            value = source_mapping[key]

            if '.' in key:
                imports.add(DotDict)

            if isinstance(value, Option):
                value = value.value

            if isclass(value) or ismodule(value) or isfunction(value):
                imports.add(value)
            else:
                try:
                    imports.add(value.__class__)
                except AttributeError:
                    # it's not a class instance
                    pass

        print >>output_stream, "# generated Python configman file\n"
        sorted_imports = sorted(
            get_import_for_type(an_import)
            for an_import in imports
        )
        for an_import_as_string in sorted_imports:
            if an_import_as_string:
                print >>output_stream, an_import_as_string

        sorted_keys = sorted(
            source_mapping.keys_breadth_first(include_dicts=True)
        )
        for key in sorted_keys:
            value = source_mapping[key]
            if isinstance(value, Namespace):
                ValueSource.write_namespace(key, value, output_stream)
            elif isinstance(value, Option):
                ValueSource.write_option(key, value, output_stream)
            else:
                ValueSource.write_bare_value(key, value, output_stream)
