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
import copy
import itertools

from configman.dontcare import dont_care
from configman.option import Option
from configman.dotdict import DotDict
from configman.converters import boolean_converter, to_str

from configman.argparse_ import (
    ControlledErrorReportingArgumentParser,
    ArgumentParser
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
    """The ValueSource implementation for the getopt module.  This class will
    interpret an argv list of commandline arguments using getopt."""
    #--------------------------------------------------------------------------
    def __init__(self, source, conf_manager):
        self.source = source
        self.parsers = []
        self.argv_source = tuple(conf_manager.argv_source)
        if (source is argparse
            or issubclass_with_no_type_error(source, argparse.ArgumentParser)
        ):
            self.parser = None
            self.parser_class = ControlledErrorReportingArgumentParser
            self.known_args = set()
        elif isinstance(source, ArgumentParser):
            self.parser = None
            self.parsers = [source]
            self.parser_class = ControlledErrorReportingArgumentParser
            self.known_args = set(action.dest for action in source._actions)
            source.parse_through_configman = False
            self._brand_parser(source)
        else:
            raise CantHandleTypeException()

    # frequently, command line data sources must be treated differently.  For
    # example, even when the overall option for configman is to allow
    # non-strict option matching, the command line should not arbitrarily
    # accept bad command line switches.  The existance of this key will make
    # sure that a bad command line switch will result in an error without
    # regard to the overall --admin.strict setting.
    command_line_value_source = True

    def _brand_parser(self, parser):
        try:
            parser._brand = self._brand
        except AttributeError:
            self._brand = 0
            parser._brand = self._brand
        #print "BBBBBB", self._brand, parser._actions
        self._brand += 1


    #--------------------------------------------------------------------------
    def _get_known_args(self, conf_manager):
        return set(
            x
            for x in conf_manager.option_definitions.keys_breadth_first()
        )
    #--------------------------------------------------------------------------
    def _option_to_command_line_str(self, an_option, key):
        if an_option.is_argument:
            if an_option.number_of_values is not None:
                return to_str(an_option.value).split(',')
            return to_str(an_option.value)
        if an_option.number_of_values == 0:
            return None
        if an_option.from_string_converter in (bool, boolean_converter):
            if an_option.value:
                return "--%s" % key
            return None
        return "--%s=%s" % (
            key,
            to_str(an_option.value)
        )

    #--------------------------------------------------------------------------
    def create_fake_args(self, config_manager):
        # all of this is to keep argparse from barfing if the minumum number
        # of required arguments is not in place at run time.  It may be that
        # some config file or environment will bring them in later.   argparse
        # needs to cope using this placebo argv
        args = [
            self._option_to_command_line_str(
                config_manager.option_definitions[key],
                key
            )
            for key in config_manager.option_definitions.keys_breadth_first()
            if isinstance(
                config_manager.option_definitions[key],
                Option
            ) and config_manager.option_definitions[key].is_argument
        ]
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
        except AttributeError:
            return final_arg_list

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        if ignore_mismatches:
            if self.parser is None:
                self.parser = self._create_new_argparse_instance(
                    self.parser_class,
                    config_manager,
                    False,
                    self.parsers,
                )
            #print "about to parse_known_args", self.parser._brand, self.parser.parse_through_configman
            namespace_and_extra_args = self.parser.parse_known_args(
                args=self.argv_source
            )
            try:
                argparse_namespace, self.extra_args =  namespace_and_extra_args
                #print "EXTRAS", self.extra_args
            except TypeError:
                argparse_namespace = argparse.Namespace()
            #print "pushing onto stack", self.parser._brand, self.parser._actions
            self.parsers = [self.parser]
            self.parser = None
        else:
            fake_args = self.create_fake_args(config_manager)
            #print "final", fake_args
            self.parser = self._create_new_argparse_instance(
                self.parser_class,
                config_manager,
                True,
                self.parsers,
            )
            #print "about to parse_args", self.parser._brand, self.parser.parse_through_configman
            argparse_namespace = self.parser.parse_args(
                args=fake_args,
                #args=self.argv_source,
            )
        return DotDict(argparse_namespace.__dict__)

    #--------------------------------------------------------------------------
    def _create_new_argparse_instance(
        self,
        parser_class,
        config_manager,
        create_auto_help,
        parents,
    ):
        #print "new parser with %s parents" % len(parents)
        #for p in parents:
            #print "   ", p._brand
        a_parser = parser_class(
            prog=config_manager.app_name,
            version=config_manager.app_version,
            description=config_manager.app_description,
            add_help=create_auto_help,
            parents=parents,
        )
        self._brand_parser(a_parser)
        self._setup_argparse(a_parser, config_manager)
        #print 'created ', a_parser._brand, a_parser._actions
        return a_parser

    #--------------------------------------------------------------------------
    def _setup_argparse(self, parser, config_manager):
        current_args = self._get_known_args(config_manager)
        new_args = current_args - self.known_args
        #print "CURRENT", current_args
        #print "KNOWN  ", self.known_args
        #print "NEW    ", new_args
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            #print "working on ", opt_name
            if opt_name not in new_args :
                #print 'skipping'
                continue
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
                    kwargs.type = an_opt.from_string_converter

                kwargs.default = dont_care(an_opt.default)
                kwargs.help = an_opt.doc
                if not an_opt.is_argument:
                    kwargs.dest = opt_name

                parser.add_argument(*args, **kwargs)
        self.known_args = current_args.union(new_args)
        #print "COPY:   ", self.parser._positionals._actions


    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
