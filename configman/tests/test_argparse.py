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
    from configman.argparse_ import (
        ControlledErrorReportingArgumentParser,
        ArgumentParser,
        argparse
    )
except ImportError:
    raise SkipTest

from mock import Mock
from os import environ

from configman.config_file_future_proxy import ConfigFileFutureProxy
from configman.dotdict import DotDict
from configman.dontcare import dont_care


#==============================================================================
class TestCaseForControlledErrorReportingArgumentParser(TestCase):
    def test_controlled_error_reporting_constructor(self):
        an_argparser = ControlledErrorReportingArgumentParser(add_help=True)
        self.assertFalse(an_argparser.parse_through_configman)
        self.assertEqual(an_argparser._actions[0].dest, 'help')

    def test_controlled_error_reporting_error_with_help(self):
        an_argparser = ControlledErrorReportingArgumentParser(add_help=False)
        an_argparser.print_usage = Mock()
        an_argparser.exit = Mock()
        an_argparser.error("I'm sorry, Dave, I can't do that.")
        self.assertFalse(an_argparser.print_usage.called)
        self.assertFalse(an_argparser.exit.called)

        an_argparser.print_usage.reset_mock()
        an_argparser.exit.reset_mock()
        an_argparser = ControlledErrorReportingArgumentParser(add_help=True)
        an_argparser.print_usage = Mock()
        an_argparser.exit = Mock()
        an_argparser.error("I'm sorry, Dave, I can't do that.")
        self.assertTrue(an_argparser.print_usage.called)
        self.assertTrue(an_argparser.exit.called)

        an_argparser.print_usage.reset_mock()
        an_argparser.exit.reset_mock()
        an_argparser = ControlledErrorReportingArgumentParser(add_help=False)
        an_argparser.print_usage = Mock()
        an_argparser.exit = Mock()
        an_argparser.error("whatever you are doing, it is not allowed")
        self.assertTrue(an_argparser.print_usage.called)
        self.assertTrue(an_argparser.exit.called)

        an_argparser.print_usage.reset_mock()
        an_argparser.exit.reset_mock()
        an_argparser = ControlledErrorReportingArgumentParser(add_help=False)
        an_argparser.print_usage = Mock()
        an_argparser.exit = Mock()
        an_argparser.error("consider yourself ignored")
        self.assertTrue(an_argparser.print_usage.called)
        self.assertTrue(an_argparser.exit.called)

        an_argparser.print_usage.reset_mock()
        an_argparser.exit.reset_mock()
        an_argparser = ControlledErrorReportingArgumentParser(add_help=False)
        an_argparser.print_usage = Mock()
        an_argparser.exit = Mock()
        an_argparser.error("well, that was expected")
        self.assertTrue(an_argparser.print_usage.called)
        self.assertTrue(an_argparser.exit.called)


#==============================================================================
class MyParser(ArgumentParser):
    def error(self, message):
        pass
    def exit(self):
        pass


#==============================================================================
class TestCaseForArgumentParser(TestCase):
    def test_controlled_error_reporting_constructor(self):
        an_argparser = ArgumentParser(add_help=True)
        self.assertTrue(an_argparser.parse_through_configman)
        self.assertRaises(IndexError, lambda: an_argparser._actions[0])
        self.assertTrue(environ in an_argparser.value_source_list)
        self.assertTrue(
            ConfigFileFutureProxy in an_argparser.value_source_list
        )
        self.assertTrue(an_argparser in an_argparser.value_source_list)


    def test_adding_arguments(self):
        an_argparser = ArgumentParser(add_help=True)
        self.assertEqual(0, len(an_argparser._actions))
        a = an_argparser.add_argument(
            '-s', action='store', dest='simple_value',
            default=17, help='Store a simple value'
        )
        self.assertTrue(a.default.dont_care())

        a = an_argparser.add_argument(
            '-c', action='store_const',
            dest='constant_value',
            #default='default',
            const='value-to-store',
            help='Store a constant value'
        )

        a = an_argparser.add_argument(
            '-t',
            action='store_true',
            default=False,
            dest='boolean_switch',
            help='Set a switch to true'
        )
        self.assertFalse(a.default.as_bare_value())

        a = an_argparser.add_argument(
            '-f',
            action='store_false',
            default=False,
            dest='boolean_switch',
            help='Set a switch to false'
        )
        self.assertFalse(a.default.as_bare_value())

        a = an_argparser.add_argument(
            '-a', action='append', dest='collection',
            default=[],
            help='Add repeated values to a list',
        )
        self.assertTrue(a.default.dont_care())

        a = an_argparser.add_argument(
            '-A', action='append_const', dest='const_collection',
            const='value-1-to-append',
            default=[],
            help='Add different values to list'
        )
        #self.assertTrue(a.default.dont_care())

        a = an_argparser.add_argument(
            '-B', action='append_const', dest='const_collection',
            const='value-2-to-append',
            help='Add different values to list'
        )
        self.assertTrue(a.default.as_bare_value() is None)

    def create_testing_argparser(self):
        an_argparser = ArgumentParser()
        an_argparser.print_usage = Mock()
        an_argparser.exit = Mock()
        self.assertEqual(0, len(an_argparser._actions))
        an_argparser.add_argument(
            '-s',
            action='store',
            dest='simple_value',
            default=17,
            help='Store a simple value'
        )
        a = an_argparser.add_argument(
            '-c',
            action='store_const',
            dest='constant_value',
            const='value-to-store',
            help='Store a constant value'
        )
        an_argparser.add_argument(
            '-t',
            action='store_true',
            default=False,
            dest='boolean_switch',
            help='Set a switch to true'
        )
        an_argparser.add_argument(
            '-f',
            action='store_false',
            default=False,
            dest='boolean_switch',
            help='Set a switch to false'
        )
        an_argparser.add_argument(
            '-a',
            action='append', dest='collection',
            default=[],
            help='Add repeated values to a list',
        )
        an_argparser.add_argument(
            '-A',
            action='append_const',
            dest='const_collection',
            const='value-1-to-append',
            default=[],
            help='Add different values to list'
        )
        an_argparser.add_argument(
            '-B',
            action='append_const',
            dest='const_collection',
            const='value-2-to-append',
            help='Add different values to list'
        )
        an_argparser.value_source_list = [an_argparser]
        return an_argparser

    def test_parse_args_1(self):
        an_argparser = self.create_testing_argparser()

        an_argparser.parse_through_configman = True
        result = an_argparser.parse_args(args=['-c'])
        self.assertTrue(isinstance(result, DotDict))
        self.assertEqual(result.constant_value, 'value-to-store')
        #self.assertFalse(hasattr(result.constant_value, 'dont_care'))

        an_argparser.parse_through_configman = True
        result = an_argparser.parse_args(args=[])
        self.assertTrue(isinstance(result, DotDict))
        #self.assertTrue(result.constant_value.dont_care())
        self.assertTrue(result.constant_value is None)
        #self.assertTrue(result.boolean_switch.dont_care())
        #self.assertTrue(result.collection.dont_care())
        #self.assertTrue(result.const_collection.dont_care())

        an_argparser.parse_through_configman = True
        result = an_argparser.parse_args(args=['-t'])
        self.assertTrue(isinstance(result, DotDict))
        self.assertTrue(result.boolean_switch)
        #self.assertTrue(result.constant_value.dont_care())

        an_argparser.parse_through_configman = True
        result = an_argparser.parse_args(args=['-a', '1', '-a', '2'])
        self.assertTrue(isinstance(result, DotDict))
        self.assertEqual(result.collection, ['1', '2'])

        an_argparser.parse_through_configman = True
        #result = an_argparser.parse_args(args=['-A', '-B'])
        result = an_argparser.parse_args(args=['-A', '-B'])
        self.assertTrue(isinstance(result, DotDict))
        self.assertEqual(
            result.const_collection,
            ['value-1-to-append', 'value-2-to-append']
        )

    def test_parse_args_2(self):
        an_argparser = self.create_testing_argparser()

        an_argparser.parse_through_configman = False
        result = an_argparser.parse_args(args=['-c'])
        self.assertTrue(isinstance(result, argparse.Namespace))
        self.assertEqual(result.constant_value, 'value-to-store')
        self.assertFalse(hasattr(result.constant_value, 'dont_care'))

        an_argparser.parse_through_configman = False
        result = an_argparser.parse_args(args=[])
        self.assertTrue(isinstance(result, argparse.Namespace))
        self.assertTrue(result.constant_value.dont_care())
        self.assertTrue(result.constant_value.as_bare_value() is None)
        self.assertTrue(result.boolean_switch.dont_care())
        self.assertTrue(result.collection.dont_care())
        self.assertTrue(result.const_collection.dont_care())

        an_argparser.parse_through_configman = False
        result = an_argparser.parse_args(args=['-t'])
        self.assertTrue(isinstance(result, argparse.Namespace))
        self.assertTrue(result.boolean_switch)
        self.assertTrue(result.constant_value.dont_care())

        an_argparser.parse_through_configman = False
        result = an_argparser.parse_args(args=['-a', '1', '-a', '2'])
        self.assertTrue(isinstance(result, argparse.Namespace))
        self.assertEqual(result.collection, ['1', '2'])

        an_argparser.parse_through_configman = False
        #result = an_argparser.parse_args(args=['-A', '-B'])
        result = an_argparser.parse_args(args=['-A', '-B'])
        self.assertTrue(isinstance(result, argparse.Namespace))
        self.assertEqual(
            result.const_collection,
            ['value-1-to-append', 'value-2-to-append']
        )




