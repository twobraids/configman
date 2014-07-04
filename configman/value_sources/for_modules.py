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
from functools import partial

from configman.namespace import Namespace
from configman.option import Option, Aggregation
from configman.converters import (
    to_str,
    class_converter,
    converter_service,
    ConverterService,
    AnyInstanceOf,
    dontcare_to_str,
    _arbitrary_object_to_string,
)
from configman.dontcare import DontCare
file_name_extension = 'py'


can_handle = (
    types.ModuleType,
)

local_converter = ConverterService(
    fallback_converter_service=converter_service
)


#--------------------------------------------------------------------------
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
            local_converter.convert(x, objective_type_key='str')
            for x in a_list
        ),
        close_bracket_char
    )
local_converter.register_converter(
    AnyInstanceOf(list),
    sequence_to_string,
    objective_type=str
)
local_converter.register_converter(
    AnyInstanceOf(tuple),
    sequence_to_string,
    objective_type=str
)


#--------------------------------------------------------------------------
def string_to_string(a_string):
    quote = '"'
    if '"' in a_string:
        quote = "'"
    if "'" in a_string:
        quote = '"""'
    if "/n" in a_string:
        quote = "'''"
    return "%s%s%s" % (quote, a_string, quote)
local_converter.register_converter(
    AnyInstanceOf(str),
    string_to_string,
    objective_type=str
)

#--------------------------------------------------------------------------
def datetime_to_string(d):
    return "datetime.datetime(year=%s, month=%s, day=%s, hour=%s, " \
        "minute=%s, second=%s)" % (
            d.year,
            d.month,
            d.day,
            d.hour,
            d.minute,
            d.second,
        )
local_converter.register_converter(
    AnyInstanceOf(datetime.datetime),
    datetime_to_string,
    objective_type=str
)


#--------------------------------------------------------------------------
def date_to_string(d):
    return "datetime.date(year=%s, month=%s, day=%s)" % (
            d.year,
            d.month,
            d.day,
        )
local_converter.register_converter(
    AnyInstanceOf(datetime.date),
    date_to_string,
    objective_type=str
)

#--------------------------------------------------------------------------
def timedelta_to_string(d):
    return "datetime.timedelta(days=%s, seconds=%s)" % (
            d.days,
            d.seconds,
        )
local_converter.register_converter(
    AnyInstanceOf(datetime.timedelta),
    timedelta_to_string,
    objective_type=str
)

#--------------------------------------------------------------------------
def type_to_string(t):
    s = _arbitrary_object_to_string(t)
    return string_to_string(s)
local_converter.register_converter(
    AnyInstanceOf(type),
    type_to_string,
    str
)

##--------------------------------------------------------------------------
#local_converter.register_converter(
    #AnyInstanceOf(DontCare),
    #partial(dontcare_to_str, a_converter_service=local_converter),
    #objective_type=str
#)


#==============================================================================
class ValueSource(object):
    #--------------------------------------------------------------------------
    def __init__(self, source, the_config_manager=None):
        if isinstance(source, basestring):
            source = class_converter(source)
        module_dict = source.__dict__.copy()
        to_remove = [
            k for k in module_dict.keys()
            if k.startswith('__') and k != "__doc__"
        ]
        for a_key in to_remove:
            del module_dict[a_key]
        self.source = module_dict

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        return self.source

    #--------------------------------------------------------------------------
    @staticmethod
    def write_option(key, an_option, output_stream):
        value = local_converter.convert(
            an_option.value,
            objective_type_key='str'
        )
        print >>output_stream, '\n',
        if an_option.doc:
            print >>output_stream, '# %s' % an_option.doc
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
        print >>output_stream, "# generated Python configman file\n"
        print >>output_stream, "import datetime"
        print >>output_stream, "from configman.dotdict import DotDict\n"
        sorted_keys = sorted(
            source_mapping.keys_breadth_first(include_dicts=True)
        )
        for key in sorted_keys:
            value = source_mapping[key]
            if isinstance(value, Namespace):
                ValueSource.write_namespace(key, value, output_stream)
            elif isinstance(value, Option):
                ValueSource.write_option(key, value, output_stream)
