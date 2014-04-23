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

from configman.dontcare import DontCare
from configman.option import Option
from configman.dotdict import DotDict
from configman.converters import boolean_converter

from source_exceptions import CantHandleTypeException

is_command_line_parser = True

can_handle = (
    argparse.ArgumentParser,   # not yet implemented
    argparse,
)

#==============================================================================
class ValueSource(object):
    """The ValueSource implementation for the getopt module.  This class will
    interpret an argv list of commandline arguments using getopt."""
    #--------------------------------------------------------------------------
    def __init__(self, source, the_config_manager=None):
        self.source = source
        if source is argparse:
            # need to setup an arg parser based on what is already known
            self.parser = None
            self.argv_source = tuple(the_config_manager.argv_source)
        elif isinstance(source, argparse.ArgumentParser):
            self.parser = source
            raise NotImplemented
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
        if ignore_mismatches:
            if self.source is argparse:
                self.parser = self._create_new_argparse_instance(
                    argparse,
                    config_manager,
                    create_auto_help=False,
                )
            argparse_namespace, args = self.parser.parse_known_args(
                args=self.argv_source
            )
        else:
            if self.source is argparse:
                self.parser = self._create_new_argparse_instance(
                    argparse,
                    config_manager,
                    create_auto_help=True,
                )
            argparse_namespace = self.parser.parse_args(
                args=self.argv_source
            )

        return DotDict(argparse_namespace.__dict__)

    #--------------------------------------------------------------------------
    def _create_new_argparse_instance(
        self,
        argparse_module,
        config_manager,
        create_auto_help,
    ):
        a_parser = argparse_module.ArgumentParser(
            add_help=create_auto_help,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            an_opt = config_manager.option_definitions[opt_name]
            if isinstance(an_opt, Option):
                if an_opt.is_argument:  # is positional argument
                    option_name = opt_name
                else:
                    option_name = '--%s' % opt_name

                if an_opt.short_form:
                    option_short_form = '-%s' % an_opt.short_form
                    args = (option_name, option_short_form)
                else:
                    option_short_form = None
                    args = (option_name,)

                kwargs = DotDict()
                if an_opt.from_string_converter in (bool, boolean_converter):
                    kwargs.action = 'store_true'
                else:
                    kwargs.action = 'store'

                kwargs.default = DontCare(an_opt.default)
                kwargs.help = an_opt.doc
                kwargs.dest = opt_name

                a_parser.add_argument(*args, **kwargs)

        return a_parser

    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
