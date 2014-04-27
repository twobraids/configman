import argparse
from os import environ

from configman.config_manager import ConfigurationManager
from configman.config_file_future_proxy import ConfigFileFutureProxy

#------------------------------------------------------------------------------
class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.value_source_list = [environ, ConfigFileFutureProxy, argparse]

    def parse_args(self, args=None, namespace=None):
        configuration_manager = ConfigurationManager(
            definition_source=[self],
            values_source_list=self.value_source_list,
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
        )
        return configuration_manager.get_config()
