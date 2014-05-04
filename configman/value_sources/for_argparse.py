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

from configman.dontcare import dont_care
from configman.option import Option
from configman.dotdict import DotDict, iteritems_breadth_first
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
        if (
            source is argparse
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
            source.parse_through_configman = False  # say no to recursion here
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

    #--------------------------------------------------------------------------
    def _brand_parser(self, parser):
        """we create several parser instances.  It has proven handy to mark
        them"""
        try:
            parser._brand = self._brand
        except AttributeError:
            self._brand = 0
            parser._brand = self._brand
        self._brand += 1

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
            if (an_option.number_of_values is not None
                and isinstance(an_option.value, collections.Sequence)
            ):
                return [to_str(x) for x in an_option.value]
            return str(an_option.value)
        if an_option.number_of_values == 0:
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
        print 'creating fake args'
        # all of this is to keep argparse from barfing if the minumum number
        # of required arguments is not in place at run time.  It may be that
        # some config file or environment will bring them in later.   argparse
        # needs to cope using this placebo argv
        for key in config_manager.option_definitions.keys_breadth_first():
            an_option = config_manager.option_definitions[key]
            print "   ", key, an_option.name, an_option.default, type(an_option.default)
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
        print "args:", args
        flattened_arg_list = []
        for x in args:
            if isinstance(x, list):
                flattened_arg_list.extend(x)
            else:
                flattened_arg_list.append(x)
        print "flattened", flattened_arg_list
        final_arg_list = [
            x.strip()
            for x in flattened_arg_list
            if x is not None and x.strip() != ''
        ]
        print 'final:', final_arg_list
        try:
            print 'plus+', self.extra_args
            return final_arg_list + self.extra_args
        except AttributeError:
            return final_arg_list

    #--------------------------------------------------------------------------
    @staticmethod
    def _val_as_str(value):
        try:
            # the value may be a modified 'dont_care' object,
            # that means we do care now and we should get the modified value &
            # return it as a bare value converted to a string
            return to_str(value.as_bare_value())
        except AttributeError:
            # 'dont_care' doesn't exist - this must be not be dont_care
            pass
        return to_str(value)

    #--------------------------------------------------------------------------
    @staticmethod
    def _we_care_about_this_value(value):
        """we want this value source to only return items that were not
        the unchanged defaults.  If this test succeeds, then the value is not
        the default and should be returned to configman.  If the test returns
        False, then argparse is just returning the default that configman
        already knows about.
        """
        try:
            return not value.dont_care()
        except AttributeError:
            return True

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        print "enter get_values"
        if ignore_mismatches:
            if self.parser is None:
                print "enter top section", self.parsers
                self.parser = self._create_new_argparse_instance(
                    self.parser_class,
                    config_manager,
                    False,
                    self.parsers,
                )
                # DEBUG --------
                print "  created new parser: p%0d" % self.parser._brand
                for i, action in enumerate(self.parser._actions):
                    print "action #%02d" % i
                    print "BEFORE p%02d " % self.parser._brand, action.dest, action.default, type(action.default)
                    print "             ", action.type
                print "  start parsing", self.argv_source
            try:
                namespace_and_extra_args = self.parser.parse_known_args(
                    args=self.argv_source
                )
            except Exception, x:
                print x

            print "  done parsing"
            try:
                argparse_namespace, self.extra_args = namespace_and_extra_args
            except TypeError:
                argparse_namespace = argparse.Namespace()
            self.parsers = [self.parser]
            self.parser = None
        else:
            fake_args = self.create_fake_args(config_manager)
            print "entering middle section\ncreating final parser with parents", self.parsers[0]._brand, len(
                                                                                                            self.parsers)
            self.parser = self._create_new_argparse_instance(
                self.parser_class,
                config_manager,
                True,
                self.parsers,
            )
            print "final processor p%02d about to parse" % self.parser._brand
            print fake_args
            for i, an_action in enumerate(self.parser._actions):
                print i, an_action
            argparse_namespace = self.parser.parse_args(
                args=fake_args,
            )
            print "    ", argparse_namespace.const_collection, type(argparse_namespace.const_collection)

        d = DotDict()
        print "enter get_values bottom section"
        for key, value in iteritems_breadth_first(argparse_namespace.__dict__):
            if key == 'const_collection':
                print "AFTER p%02d" % self.parsers[0]._brand, value, type(
                                                                                 value)
            if self._we_care_about_this_value(value):
                #print key
                #d[key] = value
                print value, type(value)
                d[key] = self._val_as_str(value)  # TODO: we ought to let
                                                  # argpars create it's own
                                                  # real values
                #print self._val_as_str(value)
        print "done with get_values"
        return d

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
        self._brand_parser(a_parser)
        self._setup_argparse(a_parser, config_manager)
        return a_parser

    #--------------------------------------------------------------------------
    def _setup_argparse(self, parser, config_manager):
        current_args = self._get_known_args(config_manager)
        new_args = current_args - self.known_args
        print "parser p%02d" % parser._brand, "being setup with ", new_args
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            if opt_name not in new_args:
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
                    args = (option_name,)

                kwargs = DotDict()
                if an_opt.from_string_converter in (bool, boolean_converter):
                    kwargs.action = 'store_true'
                else:
                    kwargs.action = 'store'
                    kwargs.type = to_str

                kwargs.default = dont_care(to_str(an_opt.default))  # TODO: not original value?
                kwargs.help = an_opt.doc
                if not an_opt.is_argument:
                    kwargs.dest = opt_name

                parser.add_argument(*args, **kwargs)
        self.known_args = current_args.union(new_args)

    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
