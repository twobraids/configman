import argparse

from configman.config_manager import ConfigurationManager

#------------------------------------------------------------------------------
class ArgumentParser(argparse.ArgumentParser):

    def parse_args(self, args=None, namespace=None):
        configuration_manager = ConfigurationManager(
            definition_source=[self],
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
        )
        return configuration_manager.get_config()