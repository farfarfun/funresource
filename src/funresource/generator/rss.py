import re
import time
from collections.abc import Iterator
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from farlog import getLogger

from funresource.db.base import Resource
from funresource.generator.base import BaseGenerate

logger = getLogger("funresource")


class RSSGenerate(BaseGenerate):
    """从 RSSHub Telegram 订阅中采集网盘资源。"""

    def __init__(self) -> None:
        """创建采集器并载入默认 RSS 地址。"""
        super().__init__()
        self.url_list: list[str] = [
            "https://rsshub.app/telegram/channel/Aliyun_4K_Movies",
            "https://rsshub.app/telegram/channel/yunpanpan",
            "https://rsshub.app/telegram/channel/shareAliyun",
            "https://rsshub.app/telegram/channel/Q66Share",
        ]

    def init(self) -> None:
        """RSS 采集无需额外初始化。"""

    def load(self) -> None:
        """RSS 数据在生成阶段按需加载。"""

    def generate(self) -> Iterator[Resource]:
        """请求全部 RSS 地址并逐条生成有效资源记录。"""
        for url in self.url_list:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"请求 RSS 失败：{url}") from exc

            feed = feedparser.parse(response.text)
            if feed.get("bozo"):
                raise ValueError(f"解析 RSS 失败：{url}: {feed.get('bozo_exception')}")

            for entry in feed["entries"]:
                try:
                    soup = BeautifulSoup(
                        entry["summary_detail"]["value"], "html.parser"
                    )
                    name = (
                        re.split(r"描述：|资源简介：", soup.find("p").text)[0]
                        .split("名称：")[1]
                        .strip()
                    )
                    yield Resource(
                        name=name,
                        url=soup.find("a", href=True)["href"],
                        update_time=datetime.fromtimestamp(
                            time.mktime(entry["published_parsed"])
                        ),
                    )
                except (
                    KeyError,
                    IndexError,
                    AttributeError,
                    TypeError,
                    ValueError,
                ) as exc:
                    logger.warning("跳过 RSS 中的无效条目，URL={}：{}", url, exc)

    def destroy(self) -> None:
        """RSS 采集无需清理临时资源。"""
