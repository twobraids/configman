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

"""This module implements a configuration value source from the commandline
implemented using argparse.  This was a difficult module to make because of
some fundemental differences with the way that configman and argparse set up
their respective priorities.

One of the primary problems is that both configman and argparse have their own
data definition specs.  Configman has Options while argparse has Actions.  Both
libraries can use their own specs, so a translation layer had to be created.
"""

import argparse

import collections

from configman.option import Option
from configman.dotdict import DotDict, iteritems_breadth_first
from configman.converters import boolean_converter, to_str

from configman.argparse_ import (
    ControlledErrorReportingArgumentParser,
    ArgumentParser,
)

from source_exceptions import CantHandleTypeException

is_command_line_parser = True

can_handle = (
    argparse.ArgumentParser,
    argparse,
)


# -----------------------------------------------------------------------------
def issubclass_with_no_type_error(potential_subclass, parent_class):
    try:
        return issubclass(potential_subclass, parent_class)
    except TypeError:
        return False


#==============================================================================
class ValueSource(object):
    """The ValueSource implementation for the argparse module.  This class will
    interpret an argv list of commandline arguments using argparse."""
    #--------------------------------------------------------------------------
    def __init__(self, source, conf_manager):
        self.source = source
        self.parent_parsers = []
        self.argparse_class = ControlledErrorReportingArgumentParser
        self.argv_source = tuple(conf_manager.argv_source)

    # frequently, command line data sources must be treated differently.  For
    # example, even when the overall option for configman is to allow
    # non-strict option matching, the command line should not arbitrarily
    # accept bad command line switches.  The existance of this key will make
    # sure that a bad command line switch will result in an error without
    # regard to the overall --admin.strict setting.
    command_line_value_source = True

    #--------------------------------------------------------------------------
    @staticmethod
    def _get_known_args(conf_manager):
        return set(
            x
            for x in conf_manager.option_definitions.keys_breadth_first()
        )

    #--------------------------------------------------------------------------
    @staticmethod
    def _option_to_command_line_str(an_option, key):
        if an_option.is_argument:
            nargs = an_option.foreign_data.argparse.kwargs.get('nargs', None)
            if (
                nargs is not None
                and isinstance(an_option.value, collections.Sequence)
            ):
                return [to_str(x) for x in an_option.value]
            if an_option.value is None:
                return []
            return str(an_option.value)
        if an_option.foreign_data.argparse.kwargs.nargs== 0:
            return None
        if an_option.from_string_converter in (bool, boolean_converter):
            if an_option.value:
                return "--%s" % key
            return None
        if an_option.value is None:
            return None
        return '--%s="%s"' % (
            key,
            to_str(an_option)
        )

    #--------------------------------------------------------------------------
    def create_fake_args(self, config_manager):
        # all of this is to keep argparse from barfing if the minumum number
        # of required arguments is not in place at run time.  It may be that
        # some config file or environment will bring them in later.   argparse
        # needs to cope using this placebo argv
        #for key in config_manager.option_definitions.keys_breadth_first():
            #an_option = config_manager.option_definitions[key]
        args = [
            self._option_to_command_line_str(
                config_manager.option_definitions[key],
                key
            )
            for key in config_manager.option_definitions.keys_breadth_first()
            if (
                isinstance(
                    config_manager.option_definitions[key],
                    Option
                )
                and config_manager.option_definitions[key].is_argument
                #and isinstance(
                    #config_manager.option_definitions[key].value,
                    #ArgparsePlaceholder
                #)
            )
        ]


        print 'create_fake_args args', args
        flattened_arg_list = []
        for x in args:
            if isinstance(x, list):
                flattened_arg_list.extend(x)
            else:
                flattened_arg_list.append(x)
        final_arg_list = [
            x.strip()
            for x in flattened_arg_list
            if x is not None and x.strip() != ''
        ]
        try:
            return final_arg_list + self.extra_args
        except (AttributeError, TypeError):
            return final_arg_list

    #--------------------------------------------------------------------------
    #@staticmethod
    #def _val_as_str(value):
        #try:
            ## the value may be a modified 'dont_care' object,
            ## that means we do care now and we should get the modified value &
            ## return it as a bare value converted to a string
            #return to_str(value.as_bare_value())
        #except AttributeError:
            ## 'dont_care' doesn't exist - this must be not be dont_care
            #pass
        #return to_str(value)

    #--------------------------------------------------------------------------
    #@staticmethod
    #def _we_care_about_this_value(value):
        #"""we want this value source to only return items that were not
        #the unchanged defaults.  If this test succeeds, then the value is not
        #the default and should be returned to configman.  If the test returns
        #False, then argparse is just returning the default that configman
        #already knows about.
        #"""
        #try:
            #return not value.dont_care()
        #except AttributeError:
            #return True

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches, object_hook=None):
        if ignore_mismatches:
            parser = self._create_new_argparse_instance(
                self.argparse_class,
                config_manager,
                False,  # create auto help
                self.parent_parsers,
            )
            namespace_and_extra_args = parser.parse_known_args(
                args=self.argv_source
            )

            try:
                argparse_namespace, self.extra_args = namespace_and_extra_args
            except TypeError:
                argparse_namespace = argparse.Namespace()
            #self.parent_parsers = [parser]
        else:
            fake_args = self.create_fake_args(config_manager)
            if '--help' in self.argv_source or "-h" in self.argv_source:
                fake_args.append("--help")
            parser = self._create_new_argparse_instance(
                self.argparse_class,
                config_manager,
                True,
                self.parent_parsers,
            )
            print 'and now the fake args:', fake_args
            argparse_namespace = parser.parse_args(
                args=fake_args,
            )
        return argparse_namespace

    #--------------------------------------------------------------------------
    def _create_new_argparse_instance(
        self,
        parser_class,
        config_manager,
        create_auto_help,
        parents,
    ):
        a_parser = parser_class(
            prog=config_manager.app_name,
            #version=config_manager.app_version,
            description=config_manager.app_description,
            add_help=create_auto_help,
            parents=parents,
        )
        self._setup_argparse(a_parser, config_manager)
        return a_parser

    #--------------------------------------------------------------------------
    def _setup_argparse(self, parser, config_manager):
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            an_option = config_manager.option_definitions[opt_name]
            if isinstance(an_option, Option):
                parser.add_argument_from_option(opt_name, an_option)

    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
