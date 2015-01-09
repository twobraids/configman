import argparse
from os import environ

#from configman.converters import dont_care
from configman.config_file_future_proxy import ConfigFileFutureProxy
from configman.dotdict import DotDict, iteritems_breadth_first
from configman.convertes import (
    str_to_instance_of_type_converters,
    str_to_list,
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
    def add_argument(self, *args, **kwargs):
        an_action = \
            super(ControlledErrorReportingArgumentParser, self).add_argument(
                *args,
                **kwargs
            )
        action_type_name = find_action_name_by_value(
                self._optionals._registries,
                an_action
            )
        target_from_string_converter = an_action.type
        if target_from_string_converter is None:
            if action_type_name == 'store_const':
                target_from_string_converter = \
                    str_to_instance_of_type_converters.get(
                        an_action.const,
                        str
                    )
            else:
                target_from_string_converter = \
                    str_to_instance_of_type_converters.get(
                        type(an_action.default),
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
            if isinstance(an_action.default, Sequence):
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
                    list_to_collection_converter=type(
                        an_action.default
                    )
                )

        # find short form
        short_form = None
        for an_option_string in kwargs.get('option_strings', []):
            try:
                if (
                    an_option_string[0] == an_option_string[1]
                    and an_option_string[0] in source.prefix_chars
                    and an_option_string[1] in source.prefix_chars
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




        option_kwargs = DotDict()
        option_kwargs.not_for_definition = an_action.default != argparse.SUPPRESS

        destination.add_option(
            name=an_action.dest,
            default=default,
            short_form=short_form,
            from_string_converter=from_string_type_converter,
            to_string_converter=converters.to_str,
            doc=an_action.help,
            number_of_values=an_action.nargs,
            is_argument=not kwargs['option_strings'],
            foreign_data=DotDict({
                'argparse.args': args,
                'argparse.kwargs': kwargs,
            })
        )
        self.required_config.add_option(

        )
        return action

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None):
        proposed_config = \
            super(ControlledErrorReportingArgumentParser, self).parse_args(
                args,
                namespace
            )
        return self._edit_config(proposed_config)

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None):
        an_argparse_namespace, extra_arguments = \
            super(ControlledErrorReportingArgumentParser, self) \
            .parse_known_args(args, namespace)
        print an_argparse_namespace
        return (
            self._edit_config(an_argparse_namespace),
            extra_arguments
        )

    #--------------------------------------------------------------------------
    def _edit_config(self, proposed_config):
        print "original", self.original_values, self.original_values.keys()
        config = DotDict()
        for key, value in iteritems_breadth_first(proposed_config.__dict__):
            try:
                if self.original_values[key] != value:
                    config[key] = value
            except KeyError, x:
                print 'KeyError: %s - not likely a problem, but I want to see how often it happens' % x
        return config



#==============================================================================
class ArgumentParser(argparse.ArgumentParser):

    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = False
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.value_source_list = [environ, ConfigFileFutureProxy, argparse]

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None):
        from configman.config_manager import ConfigurationManager
        configuration_manager = ConfigurationManager(
            definition_source=[self],
            values_source_list=self.value_source_list,
            argv_source=args,
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
        )
        conf =  configuration_manager.get_config()
        return conf

