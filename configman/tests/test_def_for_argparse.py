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


from unittest import SkipTest, TestCase

try:
    import argparse
except ImportError:
    raise SkipTest

from configman import ArgumentParser, ConfigurationManager
from configman.converters import to_str


#==============================================================================
class TestCaseForDefSourceArgparse(TestCase):

    def setup_argparse(self):
        parser = ArgumentParser(prog='hell')
        parser.add_argument(
            '-s',
            action='store',
            dest='simple_value',
            help='Store a simple value'
        )
        parser.add_argument(
            '-c',
            action='store_const',
            dest='constant_value',
            const='value-to-store',
            help='Store a constant value'
        )
        parser.add_argument(
            '-t',
            action='store_true',
            default=False,
            dest='boolean_switch',
            help='Set a switch to true'
        )
        parser.add_argument(
            '-f',
            action='store_false',
            default=False,
            dest='boolean_switch',
            help='Set a switch to false'
        )
        parser.add_argument(
            '-a',
            action='append',
            dest='collection',
            default=[],
            help='Add repeated values to a list',
        )
        parser.add_argument(
            '-A',
            action='append_const',
            dest='const_collection',
            const='value-1-to-append',
            default=[],
            help='Add different values to list'
        )
        parser.add_argument(
            '-B',
            action='append_const',
            dest='const_collection',
            const='value-2-to-append',
            help='Add different values to list'
        )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s 1.0'
        )
        return parser

    def test_parser_setup(self):
        parser = self.setup_argparse()
        actions = {}
        for x in parser._actions:
            if x.dest not in actions:
                actions[x.dest] = x
        cm = ConfigurationManager(
            definition_source=[parser],
            values_source_list=[],
        )
        options = cm.option_definitions
        for key, an_action in actions.iteritems():
            self.assertTrue(key in options)

        self.assertTrue(options.simple_value.default is None)
        self.assertEqual(options.simple_value.short_form, 's')
        self.assertTrue(
            options.simple_value.from_string_converter is str
        )
        self.assertTrue(
            options.simple_value.to_string_converter is to_str
        )
        self.assertEqual(
            options.simple_value.doc,
            actions['simple_value'].help
        )
        self.assertEqual(
            options.simple_value.number_of_values,
            actions['simple_value'].nargs
        )

        self.assertEqual(
            options.constant_value.default,
            actions['constant_value'].default.as_bare_value()
        )
        self.assertEqual(options.constant_value.short_form, 'c')
        #self.assertTrue(  # can't test - custom fn created
            #options['constant_value'].from_string_converter is some-method
        #)
        self.assertTrue(
            options.constant_value.to_string_converter is to_str
        )
        self.assertEqual(
            options.constant_value.doc,
            actions['constant_value'].help
        )
        self.assertEqual(
            options.constant_value.number_of_values,
            actions['constant_value'].nargs
        )

        #self.assertEqual(
            #options.boolean_switch.default.as_bare_value(),
            #actions['boolean_switch'].const
        #)
        #self.assertEqual(options.boolean_switch.short_form, 't')
        #self.assertTrue(  # can't verify correct corverter - custom fn created
            #options['boolean_switch'].from_string_converter is str
        #)
        self.assertTrue(
            options.boolean_switch.to_string_converter is to_str
        )
        self.assertEqual(
            options.boolean_switch.doc,
            actions['boolean_switch'].help
        )
        self.assertEqual(
            options.boolean_switch.number_of_values,
            actions['boolean_switch'].nargs
        )

        self.assertEqual(
            options.collection.default,
            actions['collection'].default.as_bare_value()
        )
        self.assertEqual(options.collection.short_form, 'a')
        #self.assertTrue(  # can't verify correct corverter - custom fn created
            #options['collection'].from_string_converter is some-method
        #)
        self.assertTrue(
            options.collection.to_string_converter is to_str
        )
        self.assertEqual(
            options.collection.doc,
            actions['collection'].help
        )
        self.assertTrue(
            options.collection.number_of_values is not None
        )

        self.assertEqual(
            options.const_collection.default,
            actions['const_collection'].default.as_bare_value()
        )
        self.assertEqual(options.const_collection.short_form, 'A')
        #self.assertTrue(  # can't verify correct corverter - custom fn created
            #options['const_collection'].from_string_converter is some-method
        #)
        self.assertTrue(
            options.const_collection.to_string_converter is to_str
        )
        self.assertEqual(
            options.const_collection.doc,
            actions['const_collection'].help
        )
        self.assertTrue(
            options.const_collection.number_of_values is not None
        )






