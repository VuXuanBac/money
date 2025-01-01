from cmdapp.base import BaseApp
from cmdapp.core import Configuration


class MoneyApp(BaseApp):
    def __init__(self, database=None, config_path: str = None, *args, **kwargs):
        super().__init__(database, *args, **kwargs)
        self.config = Configuration(config_path or "config.txt")
