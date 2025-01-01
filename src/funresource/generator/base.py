from typing import Iterator

from funutil import getLogger

from funresource.db.base import Resource, ResourceManage

logger = getLogger("funresource")


class BaseGenerate:
    def __init__(self, *args, **kwargs):
        pass

    def init(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        pass

    def generate(self, *args, **kwargs) -> Iterator[Resource]:
        pass

    def destroy(self, *args, **kwargs):
        pass

    def run(self, manage=None, *args, **kwargs):
        manage = manage or ResourceManage()
        self.init(*args, **kwargs)
        self.load(*args, **kwargs)
        manage.add_resources(self.generate(*args, **kwargs))
        self.destroy(*args, **kwargs)
