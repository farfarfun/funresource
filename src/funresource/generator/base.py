from collections.abc import Iterator

from farlog import getLogger

from funresource.db.base import Resource, ResourceManage

logger = getLogger("funresource")


class BaseGenerate:
    """资源采集器生命周期基类。"""
    def __init__(self, *args, **kwargs):
        pass

    def init(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        pass

    def generate(self, *args, **kwargs) -> Iterator[Resource]:
        """生成资源记录。"""
        pass

    def destroy(self, *args, **kwargs):
        pass

    def run(self, manage: ResourceManage | None = None, *args, **kwargs) -> None:
        """执行初始化、加载、生成和清理生命周期。"""
        manage = manage or ResourceManage()
        self.init(*args, **kwargs)
        self.load(*args, **kwargs)
        manage.add_resources(self.generate(*args, **kwargs))
        self.destroy(*args, **kwargs)
