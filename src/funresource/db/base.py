import enum
import os
from collections.abc import Iterator
from datetime import datetime

from fardb.sqlalchemy.table import BaseTable
from farlog import getLogger
from funsecret import read_secret
from sqlalchemy import (
    Enum,
    String,
    create_engine,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

logger = getLogger("funresource")


def check_tags(text: str, words: list[str], tags: list[str]) -> list[str]:
    """根据文本命中关键词时返回对应标签。"""
    if any(word.lower() in text for word in words):
        return tags
    else:
        return []


class Source(int, enum.Enum):
    """网盘资源来源。"""

    UNKNOWN = 100
    ALIYUN = 101
    KUAKE = 102
    BAIDU = 103
    XUNLEI = 104


class Status(enum.IntEnum):
    """资源上架状态。"""

    PENDING = 1  # 待上架
    ONLINE = 2  # 上架
    OFFLINE = 3  # 下架


class Resource(BaseTable):
    """可检索的网盘资源数据库记录。"""

    __tablename__ = "resource"
    source: Mapped[int] = mapped_column(
        Enum(Source), comment="来源", default=Source.ALIYUN
    )
    status: Mapped[int] = mapped_column(comment="状态", default=2)

    name: Mapped[str] = mapped_column(String(128), comment="资源名称")
    desc: Mapped[str] = mapped_column(String(512), comment="资源描述", default="")
    pic: Mapped[str] = mapped_column(String(128), comment="资源图片", default="")
    size: Mapped[int] = mapped_column(comment="大小", default=0)

    url: Mapped[str] = mapped_column(String(128), comment="分享链接")
    pwd: Mapped[str] = mapped_column(String(64), comment="密码", default="")
    update_time: Mapped[datetime] = mapped_column(
        comment="更新时间", default=datetime.now
    )
    tags: Mapped[str] = mapped_column(String(128), comment="资源类型", default="")

    def __repr__(self) -> str:
        return f"name: {self.name}, url: {self.url}, update_time: {self.update_time}"

    def _to_dict(self) -> dict:
        return {
            "name": self.name or "",
            "source": self.source or Source.ALIYUN,
            "status": self.status or 2,
            "url": self.url or "",
            "pwd": self.pwd or "",
            "update_time": self.update_time or datetime.now(),
            "tags": self.tags or "",
        }

    def _get_uid(self) -> str:
        return f"{self.name}:{self.url}"

    def _child(self) -> type["Resource"]:
        return Resource

    def upsert(self, session: Session, update_data: bool = False) -> None:
        """使用 SQLAlchemy 会话执行跨数据库 upsert。

        参数：
            session：执行写入的 SQLAlchemy 会话。
            update_data：记录已存在时是否用当前对象的字段更新它。

        返回：
            无。
        """
        data = self.to_dict()
        existing = session.get(Resource, data["uid"])
        if existing is None:
            session.add(Resource(**data))
        elif update_data:
            for key, value in data.items():
                if key != "uid":
                    setattr(existing, key, value)

    @staticmethod
    def upsert_mult(
        session: Session, res: list["Resource"], update_data: bool = False
    ) -> None:
        """批量执行跨数据库 upsert。

        参数：
            session：执行写入的 SQLAlchemy 会话。
            res：待写入的资源记录。
            update_data：记录已存在时是否更新其字段。

        返回：
            无。
        """
        for resource in res:
            resource.upsert(session, update_data=update_data)

    def is_avail(self) -> bool:
        """规范化来源和标签，并判断资源 URL 是否可写入。

        返回：
            URL 为 HTTP(S) 链接时返回 True，否则返回 False。
        """
        if self.url is not None:
            if "alipan" in self.url or "aliyundrive" in self.url:
                self.source = Source.ALIYUN
            if "quark" in self.url:
                self.source = Source.KUAKE

        tags = []
        if self.tags is not None:
            for word in ["美剧", "韩剧", "泰剧", "日剧", "国外"]:
                tags.extend(check_tags(self.tags, words=[word], tags=[word]))
            for word in ["短剧", "动画", "动漫", "电影", "综艺", "春晚"]:
                tags.extend(check_tags(self.tags, words=[word], tags=[word]))

            tags.extend(
                check_tags(self.tags, words=["电视剧", "剧集"], tags=["电视剧"])
            )

            tags.extend(
                check_tags(self.tags, words=["纪录片", "记录"], tags=["纪录片"])
            )
            tags.extend(check_tags(self.tags, words=["相声", "德云社"], tags=["相声"]))
            tags.extend(
                check_tags(self.tags, words=["小说", "书籍", "读物"], tags=["小说"])
            )

        if len(tags) == 0:
            tags.append(self.tags or "")
        tags = list(set(tags))
        self.tags = ",".join(tags)

        return self.url is not None and self.url.startswith("http")


class ResourceManage:
    """资源数据库的初始化、写入和查询入口。

    参数：
        uri：可选的 SQLAlchemy 数据库 URI；未提供时读取配置或使用本地 SQLite。
    """

    def __init__(self, uri: str | None = None) -> None:
        """创建资源管理器并初始化数据库表。

        参数：
            uri：可选的 SQLAlchemy 数据库 URI。

        返回：
            无。
        """
        self.engine = create_engine(self.get_uri(uri), echo=False)
        BaseTable.metadata.create_all(self.engine)

    @staticmethod
    def get_uri(uri: str | None = None) -> str:
        """读取配置中的数据库 URI，未配置时返回本地 SQLite URI。

        参数：
            uri：显式指定的数据库 URI，提供时直接返回。

        返回：
            可供 SQLAlchemy 使用的数据库 URI。
        """
        if uri is not None:
            return uri
        uri = read_secret("funresource", "engine", "uri")
        if uri is not None:
            return uri
        root = os.path.abspath("./funresource")
        os.makedirs(root, exist_ok=True)
        return f"sqlite:///{root}/resource.db"

    def add_resource(self, resource: Resource) -> None:
        """写入一条资源记录。

        参数：
            resource：待校验并写入的资源记录。

        返回：
            无。
        """
        with Session(self.engine) as session:
            resource.upsert(session)
            session.commit()

    def add_resources(
        self, generator: Iterator[Resource], update_data: bool = True
    ) -> None:
        """批量校验并写入资源记录。

        参数：
            generator：逐条产出待写入资源的迭代器。
            update_data：同一资源已存在时是否更新已存字段。

        返回：
            无。
        """
        with Session(self.engine) as session:
            res = []
            for size, resource in enumerate(generator):
                if not resource.is_avail():
                    continue
                res.append(resource)
                if size % 500 == 0:
                    Resource.upsert_mult(session, res, update_data=update_data)
                    session.commit()
                    res.clear()
            Resource.upsert_mult(session, res, update_data=update_data)
            session.commit()
            res.clear()

    def find(self, keyword: str) -> list[Resource]:
        """按名称正则查询资源。

        参数：
            keyword：用于匹配资源名称的正则表达式。

        返回：
            按名称匹配到的资源记录。
        """
        with Session(self.engine) as session:
            stmt = select(Resource).where(Resource.name.regexp_match(keyword))
            return [resource for resource in session.execute(stmt).scalars()]
