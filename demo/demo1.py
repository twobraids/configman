#!/usr/bin/env python
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

"""This sample application demonstrates the simlpest way to use configman."""
# this first demo shows how to use configman in the same manner that one would
# use other libraries like argparse.  We have a collection of functions that
# embody the business logic of the application.  We setup configuration
# parameters that will control the command line and config file forms.  Then
# we run the application.

import sys
from configman import ConfigurationManager, Namespace, class_converter



# the following three functions are the business logic of the application.
def echo(x):
    print x


def backwards(x):
    print x[::-1]


def upper(x):
    print x.upper()

# create the definitions for the parameters that are to come from
# the command line or config file.  First we create a container called a
# namespace for the configuration parameters.
definition_source = Namespace()
# now we start adding options to the container. This first option
# defines how we'll interpret the first argument. From the user perspective
# there are three ways to give the command to the app.
definition_source.add_option('action',
                             default=None,
                             doc='the action to take [echo, backwards, upper]',
                             short_form='a',
                             is_argument=True,
                             from_string_converter=class_converter)

# defines on the command line '--text' and '-t' swiches.  For configuration
# files, this defines a top level entry of 'text' and assigns the value
# 'Socorro Forever' to it.
definition_source.add_option('text',
                             default='Socorro Forever',
                             doc='the text input value',
                             short_form='t',
                             is_argument=True,)
# set up the manager with the option definitions along with the 'app_name' and
# 'app_description'.  They will both be used later to create  the output of the
# automatically created '--help' command line switch.
# By default, when assigning values to the options defined above, the
# ConfigurationManager will take, in turn: the default from the definition,
# any values loaded from a config file specified by the --admin.conf command
# line switch, values from the os environment and finally overrides from the
# commandline.
c = ConfigurationManager(definition_source,
                         app_name='demo1',
                         app_description=__doc__)

# fetch the DOM-like instance that gives access to the configuration info
try:
    config = c.get_config()
    config.action(config.text)
except AttributeError, x:
    print "%s is not a valid command"
except TypeError:
    print "you must specify an action"

