import argparse
from os import environ
from functools import partial

from configman.namespace import Namespace
from configman.config_file_future_proxy import ConfigFileFutureProxy
from configman.dotdict import DotDict, iteritems_breadth_first
from configman.converters import (
    str_to_instance_of_type_converters,
    str_to_list,
    arbitrary_object_to_string,
    boolean_converter,
)

# horrors
def find_action_name_by_value(registry, target):
    target_type = type(target)
    for key, value in registry['action'].iteritems():
        if value is target_type:
            if key is None:
                return 'store'
            return key
    return None

def get_args_and_values(an_action):
    args = inspect.getargspec(an_action.__class__.__init__).args
    kwargs = dict(
        (an_attr, getattr(an_action, an_attr))
        for an_attr in args if an_attr not in ('self', 'required')
    )
    return kwargs


#==============================================================================
class ArgparsePlaceholder(object):
    """instances of this class are used for placeholders in argparse options.
    We need placeholders because argparse does not give indidication to the
    calling program what arguments came from defaults and what arguments were
    actually typed by the user.

    If argparse returns one of these objects as an argument value, we'll know
    that the user didn't actually type a value for this argument."""
    pass


#==============================================================================
class ControlledErrorReportingArgumentParser(argparse.ArgumentParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(ControlledErrorReportingArgumentParser, self).__init__(
            *args, **kwargs
        )
        self.required_config = Namespace()


    #--------------------------------------------------------------------------
    def error(self, message):
        if (
            "not allowed" in message
            or "ignored" in message
            or "expected" in message
            or self.add_help
        ):
            # when we have "help" then we must also have proper error
            # processing.  Without "help", we suppress the errors by
            # doing nothing here
            super(ControlledErrorReportingArgumentParser, self).error(message)

    #--------------------------------------------------------------------------
    def add_argument_from_option(self, qualified_name, option):
        print 'adding argument', qualified_name, option.__repr__()
        if option.foreign_data is not None and "argparse" in option.foreign_data:
            args = option.foreign_data.argparse.args
            kwargs = option.foreign_data.argparse.kwargs
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
            #kwargs.type = to_str

        kwargs.default = option.default
        kwargs.help = option.doc
        if not option.is_argument:
            kwargs.dest = opt_name
        print "argparse version", args, kwargs
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
        return self._edit_config(proposed_config, object_hook)

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None, object_hook=None):
        result = super(ControlledErrorReportingArgumentParser, self) \
            .parse_known_args(args, namespace)
        try:
            an_argparse_namespace, extra_arguments = result
        except TypeError:
            an_argparse_namespace = argparse.Namespace()
            extra_arguments = result
        return (
            self._edit_config(an_argparse_namespace, object_hook),
            extra_arguments
        )

    #--------------------------------------------------------------------------
    def _edit_config(self, proposed_config, object_hook=None):
        if object_hook is None:
            object_hook = DotDict
        config = object_hook()
        for key, value in iteritems_breadth_first(proposed_config.__dict__):
            if value is ArgparsePlaceholder:
                continue
            config[key] = value
            print "tttt", key, value
        return config


#==============================================================================
class ArgumentParser(argparse.ArgumentParser):

    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = False
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.value_source_list = [environ, ConfigFileFutureProxy, argparse]
        self.required_config = Namespace()

    #--------------------------------------------------------------------------
    def add_argument(self, *args, **kwargs):
        default = kwargs.get('default', ArgparsePlaceholder)
        if default != argparse.SUPPRESS:
            kwargs['default'] = ArgparsePlaceholder

        # forward all parameters to the underlying base class
        an_action = \
            super(ArgumentParser, self).add_argument(
                *args,
                **kwargs
            )

        # get a human readable string that identifies the type of the argparse
        # action class that was created
        action_type_name = find_action_name_by_value(
                self._optionals._registries,
                an_action
            )

        # go through the features of the action to come up with equivalent
        # values for a configman option.  There will no be a perfect match,
        # however the original input gets saved in the configman Option's
        # foreign data field
        target_from_string_converter = an_action.type
        if target_from_string_converter is None:
            if action_type_name == 'store_const':
                target_from_string_converter = \
                    str_to_instance_of_type_converters.get(
                        type(an_action.const),
                        str
                    )
            else:
                target_from_string_converter = \
                    str_to_instance_of_type_converters.get(
                        type(default),
                        str
                    )
        if target_from_string_converter is type(None):
            target_from_string_converter = str

        nargs = kwargs.get('nargs', None)
        if nargs:
            target_from_string_converter = partial(
                str_to_list,
                item_converter=target_from_string_converter,
                item_separator=' ',
            )
        elif (
            kwargs.get('action', None) == 'append'
            or kwargs.get('action', None) == 'append_const'
        ):
            if isinstance(default, Sequence):
                target_from_string_converter = partial(
                    str_to_list,
                    item_converter=target_from_string_converter,
                    item_separator=',',
                )
            else:
                target_from_string_converter = partial(
                    str_to_list,
                    item_converter=target_from_string_converter,
                    item_separator=',',
                    list_to_collection_converter=type(default)
                )

        # find short form
        short_form = None
        for an_option_string in kwargs.get('option_strings', []):
            try:
                if (
                    an_option_string[0] == an_option_string[1]
                    and an_option_string[0] in source.prefix_chars
                ):
                    continue  # clearly a double prefix switch
                if (
                    an_option_string[0] in source.prefix_chars
                    and len(an_option_string) == 2
                ):
                    short_form = an_option_string[1]
            except IndexError:
                pass
                # skip this one, it has to be a single letter argument,
                # not a switch

        self.required_config.add_option(
            name=an_action.dest,
            default=default,
            doc=an_action.help,
            from_string_converter=target_from_string_converter,
            to_string_converter=arbitrary_object_to_string,
            short_form=short_form,
            is_argument=not bool(an_action.option_strings),
            not_for_definition=default != argparse.SUPPRESS,
            foreign_data=DotDict({
                'argparse.args': args,
                'argparse.kwargs': kwargs,
            })
        )
        return an_action

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None):
        from configman.config_manager import ConfigurationManager
        configuration_manager = ConfigurationManager(
            definition_source=[self.required_config],
            values_source_list=self.value_source_list,
            argv_source=args,
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
            use_auto_help=False,
        )
        conf =  configuration_manager.get_config()
        return conf

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None):
        from configman.config_manager import ConfigurationManager
        configuration_manager = ConfigurationManager(
            definition_source=[self],
            values_source_list=self.value_source_list,
            argv_source=args,
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
            use_auto_help=False,
        )
        conf =  configuration_manager.get_config()
        return conf


