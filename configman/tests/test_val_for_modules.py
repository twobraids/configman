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
import contextlib
from cStringIO import StringIO
from datetime import datetime, timedelta, date

from mock import Mock

from configman import RequiredConfig, Namespace, ConfigurationManager
from configman.config_exceptions import CannotConvertError
from configman.value_sources.for_modules import ValueSource


#==============================================================================
class Alpha(RequiredConfig):
    required_config = Namespace()
    required_config.add_option('a', doc='a', default=17)

    #--------------------------------------------------------------------------
    def __init__(self, config):
        self.config = config
        self.a = config.a


#==============================================================================
class Beta(RequiredConfig):
    required_config = Namespace()
    required_config.add_option(
        'b',
        doc='b',
        default=23
    )

    #--------------------------------------------------------------------------
    def __init__(self, config):
        self.config = config
        self.b = config.b


#==========================================================================
class TestCase(unittest.TestCase):

    #--------------------------------------------------------------------------
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

        self.assertTrue('__package__' not in v.keys())
        self.assertTrue('__builtins__' not in v.keys())
        self.assertTrue('__doc__' in v.keys())
        self.assertTrue(v.__doc__.startswith('This is a test'))

    #--------------------------------------------------------------------------
    def test_failure_1(self):
        #config_manager = Mock()
        self.assertRaises(
            CannotConvertError,
            ValueSource,
            'configman.tests.values_4_module_tests_1'
        )

    #--------------------------------------------------------------------------
    def test_failure_2(self):
        #config_manager = Mock()
        self.assertRaises(
            CannotConvertError,
            ValueSource,
            'configman/tests/test_val_for_modules.py'
        )

    #--------------------------------------------------------------------------
    def test_write_simple(self):
        rc = Namespace()
        rc.add_option(
            'a',
            default=23
        )
        rc.add_option(
            'b',
            default='this is b'
        )
        rc.namespace('n')
        rc.n.add_option(
            'x',
            default=datetime(1999, 12, 31, 11, 59)
        )
        rc.n.add_option(
            'y',
            default=timedelta(3)
        )
        rc.n.add_option(
            'z',
            default=date(1650, 10, 2)
        )

        cm = ConfigurationManager(
            [rc],
            values_source_list=[
                {
                    'a': 68,
                    'n.x': datetime(1960, 5, 4, 15, 10),
                    'n.y': timedelta(3),
                    'n.z': date(2001, 1, 1)
                }
            ]
        )
        s = StringIO()

        @contextlib.contextmanager
        def s_opener():
            yield s

        cm.write_conf('py', s_opener)
        r = s.getvalue()
        g = {}
        l = {}
        exec r in g, l
        self.assertEqual(l['a'], 68)
        self.assertEqual(l['b'], 'this is b')
        self.assertEqual(l['n'].x, datetime(1960, 5, 4, 15, 10))
        self.assertEqual(l['n'].y, timedelta(3))
        self.assertEqual(l['n'].z, date(2001, 1, 1))
