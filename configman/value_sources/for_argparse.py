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

parser_count = 0


#==============================================================================
class IntermediateConfigmanParser(argparse.ArgumentParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        self.get_parser_id()
        super(IntermediateConfigmanParser, self).__init__(
            *args, **kwargs
        )
        self.required_config = Namespace()

        self._use_argparse_add_help = kwargs.get('add_help', False)

    #--------------------------------------------------------------------------
    def get_parser_id(self):
        global parser_count
        if hasattr(self, 'id'):
            return
        self.id = "%03d" % parser_count
        parser_count += 1

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
            super(IntermediateConfigmanParser, self).error(message)

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None, object_hook=None):
        proposed_config = \
            super(IntermediateConfigmanParser, self).parse_args(
                args,
                namespace
            )
        print self.id, "about to return from parse_args"
        return self.argparse_namespace_to_dotdict(proposed_config, object_hook)

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None, object_hook=None):
        result = super(IntermediateConfigmanParser, self) \
            .parse_known_args(args, namespace)
        print self.id,  to_str(self.__class__).split('.')[-1], self.prog, 'result form parse_known_args', result
        try:
            an_argparse_namespace, extra_arguments = result
        except TypeError:
            an_argparse_namespace = argparse.Namespace()
            extra_arguments = result
        print self.id, "about to return from parse_known_args"
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
class FinalStageConfigmanParser(IntermediateConfigmanParser):

    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        self.get_parser_id()
        print self.id(), "creating FinalStageConfigmanParser"
        super(FinalStageConfigmanParser, self).__init__(
            *args, **kwargs
        )


#==============================================================================
class HelplessConfigmanParser(IntermediateConfigmanParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = False
        self.get_parser_id()
        print self.id, "creating HelplessConfigmanParser"
        super(HelplessConfigmanParser, self).__init__(
            *args, **kwargs
        )

#==============================================================================
class IntermediateConfigmanSubParser(IntermediateConfigmanParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        self.get_parser_id()
        print self.id, "creating ConfigmanSubParser"
        super(IntermediateConfigmanSubParser, self).__init__(
            *args, **kwargs
        )


#==============================================================================
class ConfigmanAdminParser(IntermediateConfigmanParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        self.get_parser_id()
        kwargs['add_help'] = False
        kwargs['prog'] = 'admin%s' % self.id
        kwargs['parents'] = []
        print self.id, "creating ConfigmanAdminParser"
        super(ConfigmanAdminParser, self).__init__(
            *args, **kwargs
        )


#==============================================================================
class ParserContainer(object):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):

        self.main_parser_args = DotDict()
        self.main_parser_args.args = args
        self.main_parser_args.kwargs = kwargs.copy()
        self.main_parser_args.kwargs.setdefault('parents', [])
        self.arguments = []
        self.subcommand = None
        self.subparser_args_list = []
        self.subparsers = {}
        self.admin_parser_args = (args, kwargs.copy())
        self.admin_arguments = []
        self._use_argparse_add_help = kwargs.get('add_help', False)
        self.get_parser_id()

    #--------------------------------------------------------------------------
    def get_parser_id(self):
        global parser_count
        if hasattr(self, 'id'):
            return
        self.id = "%03d" % parser_count
        parser_count += 1

    #--------------------------------------------------------------------------
    def create_argparse_parser(
        self,
        main_parser_class=HelplessConfigmanParser,
        subparser_class=IntermediateConfigmanSubParser,
        admin_parser_class=ConfigmanAdminParser,
    ):
        # create admin parser to be used a a parent parser
        admin_parser = admin_parser_class(
            *self.main_parser_args.args,
            **self.main_parser_args.kwargs
        )
        for admin_args in self.admin_arguments:
            admin_parser.add_argument(*admin_args.args, **admin_args.kwargs)

        # create the main parser
        self.main_parser_args.kwargs['parents'].append(admin_parser)
        main_parser = main_parser_class(
            *self.main_parser_args)
        if self.subcommand is not None:
            # add any subparsers to the parent parser
            subcommand_kwargs = copy.copy(self.subcommand.kwargs)
            subcommand_kwargs['parser_class'] = subparser_class
            subcommand_kwargs.setdefault('parents', [])
            if 'parents' in subcommand_kwargs:
                del subcommand_kwargs['parents']
            local_subparser_action = main_parser.add_subparsers(
                *self.subcommand.args,
                **subcommand_kwargs
            )
            for subparser_name in self.subparser_orignal_args.keys_breadth_first():
                subparser_kwargs = copy.copy(self.subparser_orignal_args[subparser_name].kwargs)
                if 'dest' in subparser_kwargs:
                    del subparser_kwargs['dest']
                subparser_kwargs.setdefault('parents', [])
                subparser_kwargs['parents'].append(admin_parser)
                # need to add parser, how do I get it to be my subparser class?
                local_subparser = local_subparser_action.add_parser(
                    *a_sub_parser.args,
                    **subparser_kwargs
                )
                self.subparsers[a_sub_parser.key] = local_subparser

        # add the actual arguments to the appropriate main or subparsers
        for an_argument_args in self.arguments:
            args = an_argument_args.args
            kwargs = an_argument_args.kwargs
            qualified_name = an_argument_args.qualified_name
            done = False
            for key in self.subparsers.keys():
                if qualified_name.startswith(key):
                    the_parser = self.subparsers[key]
                    the_parser.add_argument(*args, **kwargs)
                    done = True
                    break
            if done:
                continue
            main_parser.add_argument(*args, **kwargs)

        return main_parser

    #--------------------------------------------------------------------------
    def _add_argument_from_original_source(self, qualified_name, option):
        arguments = option.foreign_data.argparse
        if arguments.flags.subcommand:
            # this argument represents a subcommand, we must setup the
            # subparsers
            self.subcommand = arguments
            self.subparser_orignal_args = arguments.subparsers

        else:
            new_arguments = DotDict()
            new_arguments.args = arguments.args
            new_arguments.kwargs = copy.copy(arguments.kwargs)
            new_arguments.qualified_name = qualified_name

            if new_arguments.args == (qualified_name.split('.')[-1],):
                new_arguments.args = (qualified_name,)
            elif 'dest' in new_arguments.kwargs:
                if new_arguments.kwargs['dest'] != qualified_name:
                    new_arguments.kwargs['dest'] = qualified_name
            else:
                new_arguments.kwargs['dest'] = qualified_name

            self.arguments.append(new_arguments)

    #--------------------------------------------------------------------------
    def _add_argument_from_configman_option(self, qualified_name, option):
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

        new_arguments = DotDict()
        new_arguments.args = args
        new_arguments.kwargs = kwargs

        if qualified_name.startswith('admin'):
            self.admin_arguments.append (new_arguments)
        else:
            self.aguments.append (new_arguments)

    #--------------------------------------------------------------------------
    def add_argument_from_option(self, qualified_name, option):
        if (option.foreign_data is not None and "argparse" in option.foreign_data):
            self._add_argument_from_original_source(qualified_name, option)
        else:
            self._add_argument_from_configman_option(qualified_name, option)

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
                {
                    "main_parser_class": HelplessConfigmanParser,
                    "subparser_class": IntermediateConfigmanSubParser,
                    "admin_parser_class": ConfigmanAdminParser
                },
                config_manager,
                False,  # create auto help
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
                {
                    "main_parser_class": FinalStageConfigmanParser,
                    "subparser_class": IntermediateConfigmanSubParser,
                    "admin_parser_class": ConfigmanAdminParser
                },
                config_manager,
                True,
            )
            #print "FINAL:"
            #print '   parser', to_str(type(parser)).split('.')[-1]
            #for p in parser._actions:
                #print '      ', to_str(p)
                #try:
                    #for a in p._parsers:
                        #print '       -->', to_str(a)
                #except AttributeError:
                    #pass
            #print '       subparsers', parser._argparse_subparsers

            print 'FINAL:', parser.id
            argparse_namespace = parser.parse_args(
                args=fake_args,
            )
            print 'final', dict(argparse_namespace)
        return argparse_namespace

    #--------------------------------------------------------------------------
    def _create_new_argparse_instance(
        self,
        parser_classes,
        config_manager,
        create_auto_help,
    ):
        a_parser = ParserContainer(
            prog=config_manager.app_name,
            #version=config_manager.app_version,
            description=config_manager.app_description,
            add_help=create_auto_help,
        )
        self._setup_argparse(a_parser, parser_classes, config_manager)
        main_parser = a_parser.create_argparse_parser(**parser_classes)
        return main_parser

    #--------------------------------------------------------------------------
    def _setup_argparse(self, parser, parser_classes, config_manager):
        print 'setting up parser', parser.id
        # need to ensure that admin options are added first, since they'll
        # go into a subparser and the subparser must be complete before
        # given to any other parser as a parent
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            print "    (%s) opt_name: %s"  % (parser.id, opt_name)
            an_option = config_manager.option_definitions[opt_name]
            if isinstance(an_option, Option):
                parser.add_argument_from_option(opt_name, an_option)

    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
