import argparse
from os import environ

#from configman.converters import dont_care
from configman.config_file_future_proxy import ConfigFileFutureProxy
from configman.dotdict import DotDict, iteritems_breadth_first

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
        not_for_definition = an_action.default != argparse.SUPPRESS

        # figure out what would be an appropriate from_string_converter
        kwargs['action'] = find_action_name_by_value(
            source._optionals._registries,
            an_action
        )
        target_value_type = an_action.type
        if target_value_type is None:
            if kwargs['action'] == 'store_const':
                target_value_type = converters.get_from_string_converter(
                    an_action.const
                )
            else:
                target_value_type = type(an_action.default)
        if target_value_type is type(None) or target_value_type is None:
            target_value_type = str
        try:
            if kwargs['nargs']:
                from_string_type_converter = partial(
                    converters.list_converter,
                    target_value_type,
                    item_separator=' ',
                )
            elif (kwargs['action'] == 'append'
                  or kwargs['action'] == 'append_const'
            ):
                if isinstance(type(an_action.default), Sequence):
                    from_string_type_converter = partial(
                        converters.list_converter,
                        item_converter=
                            converters.get_from_string_converter(str),
                        item_separator=',',
                    )
                    if an_action.default is not None:
                        default = an_action.default
                else:
                    from_string_type_converter = partial(
                        converters.list_converter,
                        item_converter=
                            converters.get_from_string_converter(str),
                        item_separator=',',
                        list_to_collection_converter=type(
                            an_action.default
                        )
                    )
            else:
                from_string_type_converter = target_value_type
        except KeyError:
            from_string_type_converter = target_value_type

        # find short form
        short_form = None
        for an_option_string in kwargs['option_strings']:
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

        default = an_action.default

        destination.add_option(
            name=an_action.dest,
            default=default,
            short_form=short_form,
            from_string_converter=from_string_type_converter,
            to_string_converter=converters.to_str,
            doc=an_action.help,
            number_of_values=an_action.nargs,
            is_argument=not kwargs['option_strings'],
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

