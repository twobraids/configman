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

from configman.converters import to_str, get_from_string_converter

classes = {}

# these classes are used to support value sources that return all defined
# options no matter what happen in their internal state.  The best example
# is argparse.  The user has the option of not using absolutely all the
# command line switches on every program launch.  However, argparse doesn't
# indicate what switches actually got used.  It returns default values for
# everything that the user didn't specify but doesn't mark those defaults.

# if configman were to believe that every value provided from argparse had been
# specified by the user, the overlay system would be subverted.  Since argparse
# is on top of the Value Source chain, it's values would always override the
# values provided by other sources.

# This classes allow us to trick argparse into telling us which values came
# from the user and which are defaults that the user did not specify.

# we give the definition of arguments and their defaults to argparse.  If
# instead of simple instances of int, list, etc, we gave wrapped ones.  If the
# specified an value for a given option, we'll get that value back from
# argparse.  If, instead, the user fails to give the switch for a given
# argument, argparse will return a the default.  If we look to see if the
# returned value is one of the classes below, we know that the user didn't
# specifiy that value and it may be ignored.


#==============================================================================
class DontCare(object):
    """this is a wrapper class for intances of types that we cannot subclass
    examples: None, type, etc."""
    def __init__(self, value):
        self.modified__ = False
        self._value = value
    def __str__(self):
        return to_str(self._value)
    def __getattr__(self, key):
        return getattr(self._value, key)
    def __call__(self, *args, **kwargs):
        return self._value(*args, **kwargs)
    def __iter__(self):
        for x in self._value:
            yield x
    def append(self, item):
        print 'appending'
        self.modified__ = True
        return self._value.append(item)
    def from_string_converter(self):
        return get_from_string_converter(type(self.value))
    def dont_care(self):
        try:
            return not self.modified__
        except AttributeError:
            return True
    def as_bare_value(self):
        return self._value


#------------------------------------------------------------------------------
def dont_care(value):
    """this function returns an instance of a DontCare class for the given
    type and value provided.  If the type of the value provided is subclassable
    then an instance of a DontCareAbout_some_type will be returned.  If it is
    not subclassable, then an instance of DontCare from above will be returned.
    """
    value_type = type(value)
    try:
        if value_type is types.TypeType:
            X = DontCare
        else:
            result = classes[value_type](value)
            return result
    except KeyError:
        try:
            class X(value_type):
                def __init__(self, value):
                    super(X, self).__init__(value)
                    self.original_type = value_type
                    self.modified__ = False
                @classmethod
                def __hash__(kls):
                    return hash(kls.__name__)
                def append(self, item):
                    self.modified__ = True
                    return super(X, self).append(item)
                def from_string_converter(self):
                    return get_from_string_converter(value_type)
                def dont_care(self):
                    try:
                        return not self.modified__
                    except AttributeError:
                        return True
                def as_bare_value(self):
                    return self.original_type(self)
            X.__name__ = 'DontCareAbout_%s' % to_str(value_type)

        except TypeError, x:
            X = DontCare
    classes[value_type] = X
    x = X(value)
    x.dont_care__ = True
    return x

