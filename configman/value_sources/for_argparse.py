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

"""This module implements a configuration value source from the commandline.
It uses getopt in its implementation.  It is thought that this implementation
will be supplanted by the argparse implementation when using Python 2.7 or
greater.

This module declares that its ValueSource constructor implementation can
handle the getopt module or a list.  If specified as the getopt module, the
constructor will fetch the source of argv from the configmanager that was
passed in.  If specified as a list, the constructor will assume the list
represents the argv source."""

import argparse
import collections

from .. import dotdict
from .. import option
from .. import namespace

from source_exceptions import ValueException, CantHandleTypeException


can_handle = (
    argparse.ArgumentParser,
    argparse,  # not yet implemented
)


#==============================================================================
class ValueSource(object):
    """The ValueSource implementation for the getopt module.  This class will
    interpret an argv list of commandline arguments using getopt."""
    #--------------------------------------------------------------------------
    def __init__(self, source, the_config_manager=None):
        if source is argparse:
            raise CantHandleTypeException()
        elif isinstance(source, argparse.ArgumentParser):
            self.source = source
        else:
            raise CantHandleTypeException()

    # frequently, command line data sources must be treated differently.  For
    # example, even when the overall option for configman is to allow
    # non-strict option matching, the command line should not arbitrarily
    # accept bad command line switches.  The existance of this key will make
    # sure that a bad command line switch will result in an error without
    # regard to the overall --admin.strict setting.
    command_line_value_source = True

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        dd = dotdict.DotDict(source.parse_args())


    #--------------------------------------------------------------------------

