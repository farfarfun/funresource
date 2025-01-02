import enum
import os
from datetime import datetime
from typing import Iterator

from funsecret import read_secret
from funutil import getLogger
from sqlalchemy import (
    Enum,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

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


class Base(DeclarativeBase):
    pass


class Resource(Base):
    __tablename__ = "resource"
    id: Mapped[int] = mapped_column(primary_key=True, comment="", autoincrement=True)
    gmt_create: Mapped[datetime] = mapped_column(comment="", default=datetime.now)
    gmt_update: Mapped[datetime] = mapped_column(
        comment="", default=datetime.now, onupdate=datetime.now
    )
    source: Mapped[int] = mapped_column(
        Enum(Source), comment="来源", default=Source.ALIYUN
    )
    status: Mapped[int] = mapped_column(
        Enum(Status), comment="状态", default=Status.ONLINE
    )

    name: Mapped[str] = mapped_column(String(128), comment="资源名称")
    desc: Mapped[str] = mapped_column(String(512), comment="资源描述", default="")
    pic: Mapped[str] = mapped_column(String(128), comment="资源图片", default="")
    size: Mapped[int] = mapped_column(comment="大小", default=0)

    url: Mapped[str] = mapped_column(String(128), comment="分享链接")
    pwd: Mapped[str] = mapped_column(String(64), comment="密码", default="")
    update_time: Mapped[datetime] = mapped_column(
        String(128), comment="更新时间", default=datetime.now
    )
    tags: Mapped[str] = mapped_column(String(128), comment="资源类型", default="")

    __table_args__ = (UniqueConstraint("name", "url", name="unique_constraint"),)

    def __repr__(self) -> str:
        return f"name: {self.name}, url: {self.url}, update_time: {self.update_time}"

    @property
    def uid(self):
        return f"{self.name}:{self.url}"

    def exists(self, session: Session):
        sql = select(Resource).where(
            Resource.name == self.name and Resource.url == self.url
        )
        return session.execute(sql).first() is not None

    def upsert(self, session: Session, update_data=False):
        stmt = insert(Resource).values(**self.to_dict())
        stmt = stmt.on_duplicate_key_update(**self.to_dict())
        session.execute(stmt)

    def upsert_mult(self, session: Session, res, update_data=False):
        data = [d.to_dict() for d in res]
        stmt = insert(Resource).values(data)
        stmt = stmt.on_duplicate_key_update(
            set_={
                "name": stmt.inserted.name,
                "source": stmt.inserted.source,
                "status": stmt.inserted.status,
                "url": stmt.inserted.url,
                "pwd": stmt.inserted.pwd,
                "update_time": stmt.inserted.update_time,
                "tags": stmt.inserted.tags,
            }
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

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "gmt_create": self.gmt_create,
            "gmt_update": self.gmt_update,
            "name": self.name,
            "source": self.source,
            "status": self.status,
            "url": self.url,
            "pwd": self.pwd,
            "update_time": self.update_time or datetime.now(),
            "tags": self.tags,
        }
        for key in list(data.keys()):
            if data[key] is None:
                data.pop(key)
        return data


class ResourceManage:
    def __init__(self, uri=None):
        self.engine = create_engine(self.get_uri(uri), echo=False)
        Base.metadata.create_all(self.engine)

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
