# -*- coding: utf-8 -*-
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

import unittest
import tempfile
import datetime
import types

from configman import converters
from configman import RequiredConfig, Namespace, ConfigurationManager


##==============================================================================
## the following two classes are used in test_classes_in_namespaces_converter1
## and need to be declared at module level scope
#class Foo(RequiredConfig):
    #required_config = Namespace()
    #required_config.add_option('x', default=17)
    #required_config.add_option('y', default=23)


##==============================================================================
#class Bar(RequiredConfig):
    #required_config = Namespace()
    #required_config.add_option('x', default=227)
    #required_config.add_option('a', default=11)


## the following two classes are used in test_classes_in_namespaces_converter2
## and test_classes_in_namespaces_converter_3.  They need to be declared at
##module level scope
##==============================================================================
#class Alpha(RequiredConfig):
    #required_config = Namespace()
    #required_config.add_option('a', doc='a', default=17)

    ##--------------------------------------------------------------------------
    #def __init__(self, config):
        #self.config = config
        #self.a = config.a


##==============================================================================
#class Beta(RequiredConfig):
    #required_config = Namespace()
    #required_config.add_option(
        #'b',
        #doc='b',
        #default=23
    #)

    ##--------------------------------------------------------------------------
    #def __init__(self, config):
        #self.config = config
        #self.b = config.b


#==============================================================================
class TestCase(unittest.TestCase):

    ##--------------------------------------------------------------------------
    #def test_str_dict_keys(self):
        #function = converters.str_dict_keys
        #result = function({u'name': u'Lärs', 'age': 99, 10: 11})
        #self.assertEqual(result, {'name': u'Lärs', 'age': 99, '10': 11})

        #for key in result.keys():
            #self.assertTrue(not isinstance(key, unicode))
            #self.assertTrue(isinstance(key, str))

    #--------------------------------------------------------------------------
    def test_some_unicode_stuff(self):
        fn = converters.utf8_converter
        self.assertEqual(fn('Lärs'), u'L\xe4rs')
        self.assertEqual(fn('"""Lärs"""'), u'L\xe4rs')
        fn = converters.do_nothing
        self.assertEqual(fn(u'Lärs'), u'Lärs')
        self.assertEqual(fn(u'"""你好, says Lärs"""'), u'你好, says Lärs')
        self.assertEqual(converters.convert('Lärs', 'unicode'), u'L\xe4rs')

    ##--------------------------------------------------------------------------
    #def test_io_converter(self):
        #function = converters.io_converter
        #import sys
        #import os
        #self.assertRaises(ValueError, function, 100.0)
        #self.assertEqual(function('stdout'), sys.stdout)
        #self.assertEqual(function('STDOut'), sys.stdout)
        #self.assertEqual(function('Stderr'), sys.stderr)
        #tmp_filename = os.path.join(tempfile.gettempdir(), 'test.anything')
        #try:
            #r = function(tmp_filename)
            #self.assertTrue(hasattr(r, 'write'))
            #self.assertTrue(hasattr(r, 'close'))
            #r.write('stuff\n')
            #r.close()
            #self.assertEqual(open(tmp_filename).read(), 'stuff\n')
        #finally:
            #if os.path.isfile(tmp_filename):
                #os.remove(tmp_filename)

    #--------------------------------------------------------------------------
    def test_timedelta_converter(self):
        function = converters.timedelta_converter
        from datetime import timedelta
        self.assertEqual(function('1'), timedelta(seconds=1))
        self.assertEqual(function('2:1'), timedelta(minutes=2, seconds=1))
        self.assertEqual(
            function('3:2:1'),
            timedelta(hours=3, minutes=2, seconds=1)
        )
        self.assertEqual(
            function('4:3:2:1'),
            timedelta(days=4, hours=3, minutes=2, seconds=1)
        )
        self.assertRaises(ValueError, function, 'xxx')
        self.assertRaises(ValueError, function, 10.1)



    #--------------------------------------------------------------------------
    def test_class_converter_nothing(self):
        function = converters.class_converter
        self.assertEqual(function(''), None)

    #--------------------------------------------------------------------------
    def test_class_converter_with_whitespace(self):
        """either side whitespace doesn't matter"""
        function = converters.class_converter
        self.assertEqual(
            function("""

         configman.tests.test_converters.Foo

        """),
            Foo
        )

    ##--------------------------------------------------------------------------
    #def test_class_converter_with_builtin(self):
        #function = converters.class_converter
        #self.assertEqual(function('int'), int)
        #self.assertEqual(function('float'), float)
        #self.assertEqual(function('range'), range)
        #self.assertEqual(function('hex'), hex)

    ##--------------------------------------------------------------------------
    #def test_class_converter_with_modules(self):
        #function = converters.class_converter
        #self.assertEqual(function('unittest'), unittest)
        #self.assertEqual(function('datetime'), datetime)
        #self.assertEqual(function('configman.converters'), converters)

    ##--------------------------------------------------------------------------
    #def test_class_converter_with_classes_from_modules(self):
        #function = converters.class_converter
        #self.assertEqual(function('unittest.TestCase'), unittest.TestCase)
        #self.assertEqual(function('configman.RequiredConfig'), RequiredConfig)
        #self.assertEqual(function('configman.Namespace'), Namespace)

    ##--------------------------------------------------------------------------
    #def test_class_converter_with_functions_from_modules(self):
        #function = converters.class_converter(
            #'configman.dotdict.iteritems_breadth_first'
        #)
        #self.assertEqual(function.__name__, 'iteritems_breadth_first')

    ##--------------------------------------------------------------------------
    #def test_boolean_converter(self):
        #self.assertTrue(converters.boolean_converter('TRUE'))
        #self.assertTrue(converters.boolean_converter('"""TRUE"""'))
        #self.assertTrue(converters.boolean_converter('true'))
        #self.assertTrue(converters.boolean_converter('t'))
        #self.assertTrue(converters.boolean_converter('1'))
        #self.assertTrue(converters.boolean_converter('T'))
        #self.assertTrue(converters.boolean_converter('yes'))
        #self.assertTrue(converters.boolean_converter("'yes'"))
        #self.assertTrue(converters.boolean_converter('y'))

        #self.assertFalse(converters.boolean_converter('FALSE'))
        #self.assertFalse(converters.boolean_converter('false'))
        #self.assertFalse(converters.boolean_converter('f'))
        #self.assertFalse(converters.boolean_converter('F'))
        #self.assertFalse(converters.boolean_converter('no'))
        #self.assertFalse(converters.boolean_converter('NO'))
        #self.assertFalse(converters.boolean_converter(''))
        #self.assertFalse(converters.boolean_converter(
            #'你好, says Lärs'
        #))

        #self.assertRaises(ValueError, converters.boolean_converter, 99)

    ##--------------------------------------------------------------------------
    #def test_regex_converter(self):
        #self.assertRaises(ValueError, converters.regex_converter, 99)
        #self.assertTrue(
            #converters.regex_converter("'''.*'''").match('anything')
        #)
        #self.assertTrue(
            #converters.regex_converter("asdf").match("asdf")
        #)

    ##--------------------------------------------------------------------------
    #def test_py_obj_to_str(self):
        #function = converters._arbitrary_object_to_string
        #self.assertEqual(function(None), '')
        #from configman import tests as tests_module
        #self.assertEqual(function(tests_module), 'configman.tests')
        #self.assertEqual(function(int), 'int')

    ##--------------------------------------------------------------------------
    #def test_str_to_list_of_strings(self):
        #function = converters.list_converter
        #self.assertEqual(function(''), [])

        #self.assertEqual(
            #function('configman.tests.test_converters.TestCase'),
            #['configman.tests.test_converters.TestCase']
        #)
        #self.assertEqual(
            #function('configman.tests, configman'),
            #['configman.tests', 'configman']
        #)
        #self.assertEqual(
            #function('int, str, 123, 你好'),
            #['int', 'str', '123', '你好']
        #)

    ##--------------------------------------------------------------------------
    #def test_str_to_list_of_ints(self):
        #function = converters.list_comma_separated_ints
        #self.assertEqual(function(''), [])

        #self.assertEqual(
            #function('1, 2, 3'),
            #[1, 2, 3]
        #)

    ##--------------------------------------------------------------------------
    #def test_str_to_list_of_strs(self):
        #function = converters.list_space_separated_strings
        #self.assertEqual(function(''), [])

        #result = function("""'你好' this "is" silly""")
        #self.assertEqual(
            #result,
            #["'你好'", 'this', '"is"', 'silly']
        #)

    ##--------------------------------------------------------------------------
    #def test_sequence_to_string(self):
        #function = converters.sequence_to_string
        #self.assertEqual(function([]), '')
        #self.assertEqual(function(tuple()), '')

        #import configman
        #self.assertEqual(
            #function([configman.tests.test_converters.TestCase]),
            #'configman.tests.test_converters.TestCase'
        #)
        #self.assertEqual(
            #function([configman.tests, configman]),
            #'configman.tests, configman'
        #)
        #self.assertEqual(
            #function([int, str, 123, "你好"]),
            #'int, str, 123, 你好'
        #)

    ##--------------------------------------------------------------------------
    #def test_dict_conversions(self):
        #d = {
            #'a': 1,
            #'b': 'fred',
            #'c': 3.1415
        #}
        #s = converters.to_str(d)

        ## round  trip
        #converter_fn = converters.from_string_converters[type(d)]
        #dd = converter_fn(s)
        #self.assertEqual(dd, d)

    ##--------------------------------------------------------------------------
    #def test_classes_in_namespaces_converter_1(self):
        #converter_fn = converters.classes_in_namespaces_converter('HH%d')
        #class_list_str = (
            #'configman.tests.test_converters.Foo,'
            #'configman.tests.test_converters.Bar'
        #)
        #result = converter_fn(class_list_str)
        #self.assertTrue(hasattr(result, 'required_config'))
        #req = result.required_config
        #self.assertEqual(len(req), 2)
        #self.assertTrue('HH0' in req)
        #self.assertEqual(len(req.HH0), 1)
        #self.assertTrue('cls' in req.HH0)
        #self.assertTrue('HH1' in req)
        #self.assertEqual(len(req.HH1), 1)
        #self.assertTrue('cls' in req.HH1)
        #self.assertEqual(
            #class_list_str,
            #converters.to_str(result)
        #)

    ##--------------------------------------------------------------------------
    #def test_classes_in_namespaces_converter_2(self):
        #converter_fn = converters.classes_in_namespaces_converter('HH%d')
        #class_sequence = (Foo, Bar)
        #self.assertRaises(TypeError, converter_fn, class_sequence)

    ##--------------------------------------------------------------------------
    #def test_classes_in_namespaces_converter_3(self):
        #n = Namespace()
        #n.add_option(
            #'kls_list',
            #default=(
                #'configman.tests.test_converters.Alpha, '
                #'configman.tests.test_converters.Alpha, '
                #'configman.tests.test_converters.Alpha'
            #),
            #from_string_converter=
            #converters.classes_in_namespaces_converter('kls%d')
        #)

        #cm = ConfigurationManager(n, argv_source=[])
        #config = cm.get_config()

        #self.assertEqual(len(config.kls_list.subordinate_namespace_names), 3)
        #for x in config.kls_list.subordinate_namespace_names:
            #self.assertTrue(x in config)
            #self.assertEqual(config[x].cls, Alpha)
            #self.assertTrue('cls_instance' not in config[x])

    ##--------------------------------------------------------------------------
    #def test_classes_in_namespaces_converter_4(self):
        #n = Namespace()
        #n.add_option(
            #'kls_list',
            #default=(
                #'configman.tests.test_converters.Alpha, '
                #'configman.tests.test_converters.Alpha, '
                #'configman.tests.test_converters.Alpha'
            #),
            #from_string_converter=converters.classes_in_namespaces_converter(
                #'kls%d',
                #'kls',
                #instantiate_classes=True
            #)
        #)

        #cm = ConfigurationManager(
            #n,
            #[{
                #'kls_list': (
                    #'configman.tests.test_converters.Alpha, '
                    #'configman.tests.test_converters.Beta, '
                    #'configman.tests.test_converters.Beta, '
                    #'configman.tests.test_converters.Alpha'
                #)
            #}]
        #)
        #config = cm.get_config()

        #self.assertEqual(len(config.kls_list.subordinate_namespace_names), 4)
        #for x in config.kls_list.subordinate_namespace_names:
            #self.assertTrue(x in config)
            #self.assertTrue('kls_instance' in config[x])
            #self.assertTrue(
                #isinstance(config[x].kls_instance,
                           #config[x].kls)
            #)

    ##--------------------------------------------------------------------------
    #def test_to_str(self):
        #to_str = converters.to_str
        #self.assertEqual(to_str(int), 'int')
        #self.assertEqual(to_str(float), 'float')
        #self.assertEqual(to_str(str), 'str')
        #self.assertEqual(to_str(unicode), 'unicode')
        #self.assertEqual(to_str(bool), 'bool')
        #self.assertEqual(to_str(dict), 'dict')
        #self.assertEqual(to_str(list), 'list')
        #for key, value in converters._builtin_to_str.iteritems():
            #self.assertEqual(to_str(key), value)
        #self.assertEqual(to_str(datetime.datetime), 'datetime.datetime')
        #self.assertEqual(to_str(datetime.date), 'datetime.date')
        #self.assertEqual(to_str(datetime.timedelta), 'datetime.timedelta')
        #self.assertEqual(to_str(type), 'type')
        #self.assertEqual(to_str(types.FunctionType), 'function')
        #self.assertEqual(
            #to_str(converters._compiled_regexp_type),
            #'_sre.SRE_Pattern'
        #)
        #self.assertEqual(
            #to_str(converters._builtin_function_or_method_type),
            #'builtin_function_or_method'
        #)
        #self.assertEqual(to_str(1), '1')
        #self.assertEqual(to_str(3.1415), '3.1415')
        #self.assertEqual(
            #to_str(datetime.datetime(
                #1960,
                #5,
                #4,
                #15,
                #10
            #)),
            #'1960-05-04T15:10:00'
        #)
        #self.assertEqual(to_str(True), 'True')
        #self.assertEqual(to_str(False), 'False')
        #self.assertEqual(to_str(None), '')
        #self.assertEqual(to_str((2, False, int, max)), '2, False, int, max')

    #def test_str_quote_stripper(self):
        #a = """'"single and double quoted"'"""
        #self.assertEqual(converters.str_quote_stripper(a), 'single and double quoted')

        #a = """'single quoted'"""
        #self.assertEqual(converters.str_quote_stripper(a), 'single quoted')

        #a = '''"double quoted"'''
        #self.assertEqual(converters.str_quote_stripper(a), 'double quoted')

        #a = '"""triple quoted"""'
        #self.assertEqual(converters.str_quote_stripper(a), 'triple quoted')

        #a = "'''triple quoted'''"
        #self.assertEqual(converters.str_quote_stripper(a), 'triple quoted')

        #a = '''"trailing apostrophy'"'''
        #self.assertEqual(
            #converters.str_quote_stripper(a),
            #"trailing apostrophy'"
        #)
