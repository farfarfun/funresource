import enum
import os
from typing import Iterator

from fundb.sqlalchemy.table import BaseTable
from funsecret import read_secret
from funutil import getLogger
from sqlalchemy import (
    Enum,
    String,
    create_engine,
    select,
)
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

logger = getLogger("funresource")


def check_tags(text, words, tags):
    if any(word.lower() in text for word in words):
        return tags
    else:
        return []


class Source(int, enum.Enum):
    UNKNOWN = 100
    ALIYUN = 101
    KUAKE = 102
    BAIDU = 103
    XUNLEI = 104


class Status(enum.IntEnum):
    PENDING = 1  # 待上架
    ONLINE = 2  # 上架
    OFFLINE = 3  # 下架


class Resource(BaseTable):
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
    tags: Mapped[str] = mapped_column(String(128), comment="资源类型", default="")

    def __repr__(self) -> str:
        return f"name: {self.name}, url: {self.url}, gmt_modified: {self.gmt_modified}"

    def _to_dict(self) -> dict:
        return {
            "name": self.name or "",
            "source": self.source or "",
            "status": self.status or 2,
            "url": self.url or "",
            "pwd": self.pwd or "",
            "tags": self.tags or "",
        }

    def _get_uid(self):
        return f"{self.name}:{self.url}"

    def _child(self):
        return Resource

    @property
    def uid(self):
        return f"{self.name}:{self.url}"

    def upsert(self, session: Session, update_data=False):
        stmt = insert(Resource).values(**self.to_dict())
        stmt = stmt.on_duplicate_key_update(**self.to_dict())
        session.execute(stmt)

    def upsert_mult(self, session: Session, res, update_data=False):
        data = [d.to_dict() for d in res]
        stmt = insert(Resource).values(data)
        stmt = stmt.on_duplicate_key_update(
            name=stmt.inserted.name,
            source=stmt.inserted.source,
            status=stmt.inserted.status,
            url=stmt.inserted.url,
            pwd=stmt.inserted.pwd,
            tags=stmt.inserted.tags,
        )
        session.execute(stmt)

    def is_avail(self):
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
            tags.append(self.tags)
        tags = list(set(tags))
        self.tags = ",".join(tags)

        if self.url is None or not self.url.startswith("http"):
            return False
        return True


class ResourceManage:
    def __init__(self, uri=None):
        self.engine = create_engine(self.get_uri(uri), echo=False)
        BaseTable.metadata.create_all(self.engine)

    @staticmethod
    def get_uri(uri=None) -> str:
        if uri is not None:
            return uri
        uri = read_secret("funresource", "engine", "uri")
        if uri is not None:
            return uri
        root = os.path.abspath("./funresource")
        os.makedirs(root, exist_ok=True)
        return f"sqlite:///{root}/resource.db"

    def add_resource(self, resource: Resource):
        with Session(self.engine) as session:
            resource.upsert(session)
            session.commit()

    def add_resources(self, generator: Iterator[Resource], update_data=True):
        with Session(self.engine) as session:
            res = []
            for size, resource in enumerate(generator):
                try:
                    res.append(resource)
                    if size % 100 == 0:
                        resource.upsert_mult(session, res, update_data=update_data)
                        session.commit()
                        res.clear()
                except Exception as e:
                    logger.error(e)
            session.commit()

    def find(self, keyword):
        with Session(self.engine) as session:
            stmt = select(Resource).where(Resource.name.regexp_match(keyword))
            return [resource for resource in session.execute(stmt).scalars()]
