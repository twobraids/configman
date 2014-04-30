import argparse
from os import environ

from configman.dontcare import dont_care

from configman.config_file_future_proxy import ConfigFileFutureProxy

class ControlledErrorReportingArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(ControlledErrorReportingArgumentParser, self).__init__(
            *args, **kwargs
        )
        self.parse_through_configman = False

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
        # unresolved: is it safe to let the parser continue in an
        # error state?  We'e doing that here TODO

#------------------------------------------------------------------------------
class ArgumentParser(ControlledErrorReportingArgumentParser):

    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = False
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.value_source_list = [environ, ConfigFileFutureProxy, self]
        self.parse_through_configman = True

    def add_argument(self, *args, **kwargs):
        action = super(ArgumentParser, self).add_argument(*args, **kwargs)
        action.default = dont_care(action.default)
        return action

    def parse_args(self, args=None, namespace=None):
        if self.parse_through_configman:
            from configman.config_manager import ConfigurationManager
            configuration_manager = ConfigurationManager(
                definition_source=[self],
                values_source_list=self.value_source_list,
                app_name=self.prog,
                app_version=self.version,
                app_description=self.description,
            )
            return configuration_manager.get_config()
        else:
            return super(ArgumentParser, self).parse_args(args, namespace)


