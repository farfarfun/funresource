from collections.abc import Iterator

from farlog import getLogger

from funresource.db.base import Resource, ResourceManage

logger = getLogger("funresource")


class BaseGenerate:
    """资源采集器生命周期基类。"""

    def __init__(self) -> None:
        """创建无状态采集器。"""

    def init(self) -> None:
        """准备采集所需资源。"""

    def load(self) -> None:
        """加载采集源数据。"""

    def generate(self) -> Iterator[Resource]:
        """返回资源记录迭代器；基类默认不生成记录。"""
        return iter(())

    def destroy(self) -> None:
        """释放采集器创建的临时资源。"""

    def run(self, manage: ResourceManage | None = None) -> None:
        """按生命周期执行采集，并将结果写入指定资源管理器。"""
        manage = manage or ResourceManage()
        self.init()
        try:
            self.load()
            manage.add_resources(self.generate())
        finally:
            self.destroy()
