import enum
import os
from datetime import datetime
from typing import Iterator

from sqlalchemy import Enum, String, UniqueConstraint, create_engine, select, BIGINT
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


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
    type: Mapped[str] = mapped_column(String(128), comment="资源类型", default="")

    __table_args__ = (UniqueConstraint("name", "url", name="unique_constraint"),)

    def __repr__(self) -> str:
        return f"name: {self.name}, url: {self.url}, update_time: {self.update_time}"

    def upsert(self, session: Session):
        self.format()
        insert_stmt = insert(Resource).values(**self.to_dict())
        session.execute(
            insert_stmt.on_conflict_do_update(
                constraint="name,url", set_=self.to_dict()
            )
        )

    def format(self):
        if self.url is not None:
            if "alipan" in self.url or "aliyundrive" in self.url:
                self.source = Source.ALIYUN
            if "quark" in self.url:
                self.source = Source.KUAKE

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
            "type": self.type,
        }
        for key in list(data.keys()):
            if data[key] is None:
                data.pop(key)
        return data


class ResourceManage:
    def __init__(self, root="./funresource"):
        root = os.path.abspath(root)
        os.makedirs(root, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{root}/resource.db", echo=False)
        Base.metadata.create_all(self.engine)

    def add_resource(self, resource: Resource):
        with Session(self.engine) as session:
            resource.upsert(session)
            session.commit()

    def add_resources(self, generator: Iterator[Resource]):
        with Session(self.engine) as session:
            for resource in generator:
                resource.upsert(session)
            session.commit()

    def find(self, keyword):
        with Session(self.engine) as session:
            stmt = select(Resource).where(Resource.name.regexp_match(keyword))
            return [resource for resource in session.execute(stmt)]
