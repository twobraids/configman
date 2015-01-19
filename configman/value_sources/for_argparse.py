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
import copy

import collections

from configman.option import Option
from configman.dotdict import (
    DotDict,
    iteritems_breadth_first,
)
from configman.converters import boolean_converter, to_str
from configman.namespace import Namespace

from source_exceptions import CantHandleTypeException

is_command_line_parser = True

can_handle = (
    argparse,
)


#==============================================================================
class ControlledErrorReportingArgumentParser(argparse.ArgumentParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = False
        try:
            print 'parents', kwargs['parents']
            if len(kwargs['parents']) == 2:
                if kwargs['parents'][0] == kwargs['parents'][1]:
                    print "SAME ALERT"
                else:
                    print "DIFFERENT ALERT"
        except KeyError:
            print 'creating', to_str(self.__class__), 'with no parents'
        super(ControlledErrorReportingArgumentParser, self).__init__(
            *args, **kwargs
        )
        self.required_config = Namespace()
        self._argparse_subparsers = {}

    #--------------------------------------------------------------------------
    def error(self, message):
        if (
            "not allowed" in message
            or "ignored" in message
            or "expected" in message
            or "invalid" in message
            or self.add_help
        ):
            # when we have "help" then we must also have proper error
            # processing.  Without "help", we suppress the errors by
            # doing nothing here
            super(ControlledErrorReportingArgumentParser, self).error(message)

    #--------------------------------------------------------------------------
    def _add_parents(self, parser_kwargs):
        try:
            if hasattr(self, 'parents') and self.parents:
                new_parents = [
                    p
                    for p in parser_kwargs['parents']
                    if not isinstance(p, ConfigmanAdminParser)
                ]
                new_parents.append(p)
                kwargs['parents'] = new_parents
        except AttributeError:
            pass
            # no 'parents' we can silently ignore that

    #--------------------------------------------------------------------------
    def add_argument_from_option(self, qualified_name, option):
        if option.foreign_data is not None and "argparse" in option.foreign_data:
            args = option.foreign_data.argparse.args
            kwargs = option.foreign_data.argparse.kwargs
            if option.foreign_data.argparse.flags.subcommand:
                original_subparser_action = \
                    option.foreign_data.argparse.flags.subcommand
                kwargs['parser_class'] = ConfigmanSubParser
                #print 'creating subparser with:', dict(kwargs)
                local_subparser_action = super(
                    ControlledErrorReportingArgumentParser,
                    self
                ).add_subparsers(
                    *args,
                    **kwargs
                )
                for key, an_orginal_subparser in original_subparser_action.choices.iteritems():
                    parser_kwargs = an_orginal_subparser.original_kwargs.copy()
                    self._add_parents(parser_kwargs)
                    #parser_kwargs['add_help'] = False
                    #print "is there help?", parser_kwargs
                    local_subparser = local_subparser_action.add_parser(
                        key,
                        **parser_kwargs
                    )
                    self._argparse_subparsers[key] = local_subparser
                return local_subparser_action
            else:
                the_parser = self
                for key in self._argparse_subparsers.keys():
                    if qualified_name.startswith(key):
                        #print '%s is from a subparser %s' % (qualified_name, key)
                        the_parser = self._argparse_subparsers[key]
                        return the_parser.add_argument_from_option(
                            qualified_name,
                            option
                        )
                if args == (qualified_name.split('.')[-1],):
                    args = (qualified_name,)
                elif 'dest' in kwargs:
                    if kwargs['dest'] != qualified_name:
                        #print "no match in: ", kwargs['dest'], qualified_name
                        kwargs['dest'] = qualified_name
                else:
                    kwargs['dest'] = qualified_name
                #print 'creating argparse argument:', args, [(x, kwargs[x]) for x in kwargs.keys_breadth_first()]
                action = super(
                    ControlledErrorReportingArgumentParser,
                    self
                ).add_argument(
                    *args,
                    **kwargs
                )
            return action

        opt_name = qualified_name

        if option.is_argument:  # is positional argument
            option_name = opt_name
        else:
            option_name = '--%s' % opt_name

        if option.short_form:
            option_short_form = '-%s' % option.short_form
            args = (option_name, option_short_form)
        else:
            args = (option_name,)

        kwargs = DotDict()
        if option.from_string_converter in (bool, boolean_converter):
            kwargs.action = 'store_true'
        else:
            kwargs.action = 'store'

        kwargs.default = argparse.SUPPRESS
        kwargs.help = option.doc
        if not option.is_argument:
            kwargs.dest = opt_name
        action = \
            super(ControlledErrorReportingArgumentParser, self).add_argument(
                *args,
                **kwargs
            )
        return action

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None, object_hook=None):
        proposed_config = \
            super(ControlledErrorReportingArgumentParser, self).parse_args(
                args,
                namespace
            )
        #print 'proposed', dir(proposed_config)
        return self.argparse_namespace_to_dotdict(proposed_config, object_hook)

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None, object_hook=None):
        result = super(ControlledErrorReportingArgumentParser, self) \
            .parse_known_args(args, namespace)
        print to_str(self.__class__).split('.')[-1], self.prog, 'result form parse_known_args', result
        try:
            an_argparse_namespace, extra_arguments = result
        except TypeError:
            an_argparse_namespace = argparse.Namespace()
            extra_arguments = result
        #print 'proposed', dir(an_argparse_namespace)
        print  to_str(self.__class__).split('.')[-1], self.prog, 'extra from parse_known_args', extra_arguments
        return (
            self.argparse_namespace_to_dotdict(
                an_argparse_namespace,
                object_hook
            ),
            extra_arguments
        )

    #--------------------------------------------------------------------------
    @staticmethod
    def argparse_namespace_to_dotdict(proposed_config, object_hook=None):
        if object_hook is None:
            object_hook = DotDict
        config = object_hook()
        for key, value in proposed_config.__dict__.iteritems():
            #print "argp-namespace", key, value
            config[key] = value
        print 'ultimately returning', dict(config)
        return config

counter = 0


#==============================================================================
class ConfigmanParser(ControlledErrorReportingArgumentParser):

    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        global counter
        counter = counter + 1
        print "creating ConfigmanParser"
        admin_parser_kwargs = copy.copy(kwargs)
        admin_parser_kwargs['prog'] = 'adimn%d' % counter
        admin_parser_kwargs['parents'] = []
        self.configman_admin_parent_parser = \
            ConfigmanAdminParser(*args, **admin_parser_kwargs)
        kwargs.setdefault('parents', [])
        parent_parsers = [
            p
            for p in kwargs['parents']
            if not isinstance(p, ConfigmanAdminParser)
        ]
        parent_parsers.append(
            self.configman_admin_parent_parser
        )
        kwargs['parents'] = parent_parsers
        super(ConfigmanParser, self).__init__(
            *args, **kwargs
        )

    #--------------------------------------------------------------------------
    def add_argument_from_option(self, qualified_name, option):
        if qualified_name.startswith('admin'):
            return self.configman_admin_parent_parser.add_argument_from_option(
                qualified_name,
                option
            )
        return super(ConfigmanParser, self).add_argument_from_option(
            qualified_name,
            option
        )


#==============================================================================
class ConfigmanSubParser(ControlledErrorReportingArgumentParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        print "creating ConfigmanSubParser"
        super(ConfigmanSubParser, self).__init__(
            *args, **kwargs
        )


#==============================================================================
class ConfigmanAdminParser(ControlledErrorReportingArgumentParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        print "creating ConfigmanBareParser"
        super(ConfigmanAdminParser, self).__init__(
            *args, **kwargs
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
        self.argparse_class = ConfigmanParser
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
    #def _option_to_args_list(an_option, key):
        #if 'argparse' in an_option.foreign_data:
            #return self._option_to_args_list_with_foreign_data(
                #an_option,
                #key
            #)
        #else:
            #return self._option_to_args_list_standard(
                #an_option,
                #key
            #)

    #--------------------------------------------------------------------------
    def _option_to_args_list(self, an_option, key):
        if an_option.is_argument:
            if an_option.foreign_data is not None:
                nargs = an_option.foreign_data.argparse.kwargs.get(
                    'nargs',
                    None
                )
            else:
                if isinstance(an_option.value, basestring):
                    return an_option.value
                if an_option.to_string_converter:
                    return an_option.to_string_converter(an_option.value)
                return to_str(an_option.value)
            if (
                nargs is not None
                and isinstance(an_option.value, collections.Sequence)
            ):
                return [to_str(x) for x in an_option.value]
            if an_option.value is None:
                return []
            return to_str(an_option.value)
        #if an_option.foreign_data.argparse.kwargs.nargs == 0:
            #return None
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
        #print "----------", self.argv_source
        #for key in config_manager.option_definitions.keys_breadth_first():  # REMOVE
            #opt = config_manager.option_definitions[key]  # REMOVE
            #if isinstance(opt, Option):  # REMOVE
                #print "kkkk", key, opt.is_argument, opt.value, type(opt.value) # REMOVE
        args = [
            self._option_to_args_list(
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
            )
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
            print "CCCCC", final_arg_list + self.extra_args
            return final_arg_list + self.extra_args
        except (AttributeError, TypeError):
            print "DDDDD", final_arg_list
            return final_arg_list

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches, object_hook=None):
        if ignore_mismatches:
            print 'RESET self.extra_arg'
            self.extra_args = []
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
                argparse_namespace, unused_args = namespace_and_extra_args
                print 'extending from', self.extra_args, 'to',
                self.extra_args.extend(unused_args)
                print self.extra_args, "with", unused_args
            except TypeError:
                argparse_namespace = argparse.Namespace()
                print 'extending from', self.extra_args, 'to',
                self.extra_args.extend(namespace_and_extra_args)
                print self.extra_args, 'with', namespace_and_extra_args

            print 'intermediate', dict(argparse_namespace), self.extra_args
            print '  even though', self.argv_source
        else:
            fake_args = self.create_fake_args(config_manager)
            if '--help' in self.argv_source or "-h" in self.argv_source:
                fake_args.append("--help")

            print "fake args", fake_args
            parser = self._create_new_argparse_instance(
                self.argparse_class,
                config_manager,
                True,
                self.parent_parsers,
            )
            print "FINAL:"
            print '   parser', to_str(type(parser)).split('.')[-1]
            for p in parser._actions:
                print '      ', to_str(p)
                try:
                    for a in p._parsers:
                        print '         ', to_str(a)
                except AttributeError:
                    pass
            print '       subparsers', parser._argparse_subparsers

            argparse_namespace = parser.parse_args(
                args=fake_args,
            )
            print 'final', dict(argparse_namespace)
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
        #print 'setting up a parser'
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            #print "opt_name", opt_name
            an_option = config_manager.option_definitions[opt_name]
            if isinstance(an_option, Option):
                parser.add_argument_from_option(opt_name, an_option)

    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
