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
from cStringIO import StringIO

from mock import Mock

from configman.value_sources.for_modules import ValueSource
from configman.value_sources.source_exceptions import CantHandleTypeException
from configman.dotdict import DotDict

#==========================================================================
class TestCase(unittest.TestCase):

    def test_basic_import(self):
        config_manager = Mock()
        vs = ValueSource('configman.tests.values_for_module_tests_1')
        v = vs.get_values(config_manager, True)

        self.assertEqual(v['a'], 18)
        self.assertEqual(v['b'], [1, 2, 3, 3])
        self.assertEqual(v['c'], set(v['b']))
        self.assertEqual(v['d']['a'], v['a'])
        self.assertEqual(v['d']['b'], v['b'])
        self.assertEqual(v['d']['c'], v['c'])
        self.assertEqual(v['d']['d'], {1: 'one', 2: 'two'})
        self.assertEqual(v['foo'](1, 2, 3), '123')
        self.assertTrue('partial' in v)
        self.assertEqual(v['bar'](b=8, c=9), '1889')
        self.assertEqual(str(v['Alpha'](*list(v['c']))), '123')

        self.assertTrue('__package__' not in v)
        self.assertTrue('__builtins__' not in v)
        self.assertTrue('__doc__' in v)
        self.assertTrue(v['__doc__'].startswith('This is a test'))

    def test_failure_1(self):
        config_manager = Mock()
        self.assertRaises(
            CantHandleTypeException,
            ValueSource,
            'configman.tests.values_4_module_tests_1'
        )

    def test_failure_2(self):
        config_manager = Mock()
        self.assertRaises(
            CantHandleTypeException,
            ValueSource,
            'configman/tests/test_val_for_modules.py'
        )

    def test_write_1(self):
        config_manager = Mock()
        vs = ValueSource('configman.tests.values_for_module_tests_1')
        v = vs.get_values(config_manager, True)
        print v
        dd = DotDict()
        for k, v in v.iteritems():
            dd[k] = v
        s = StringIO()
        vs.write(dd, s)
        r = s.getvalue()
        print "------------------"
        print r



