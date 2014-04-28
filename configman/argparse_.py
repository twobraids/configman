import argparse
from os import environ

from configman.config_manager import ConfigurationManager
from configman.config_file_future_proxy import ConfigFileFutureProxy

class ControlledErrorReportingArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(ControlledErrorReportingArgumentParser, self).__init__(
            *args, **kwargs
        )
        self.suppress_errors = True

    def error(self, message):
        if self.suppress_errors:
            return
        super(ArgumentParser, self).error(message)


#------------------------------------------------------------------------------
class ArgumentParser(ControlledErrorReportingArgumentParser):

    def __init__(self, *args, **kwargs):
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.value_source_list = [environ, ConfigFileFutureProxy, argparse]
        self.parse_through_configman = True

    def parse_args(self, args=None, namespace=None):
        if self.parse_through_configman:
            configuration_manager = ConfigurationManager(
                definition_source=[self],
                values_source_list=self.value_source_list,
                app_name=self.prog,
                app_version=self.version,
                app_description=self.description,
            )
            return configuration_manager.get_config()
        else:
            super(ArgumentParser, self).parse_args(args, namespace)


