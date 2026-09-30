from collections.abc import Iterator
from datetime import datetime
from typing import TypedDict

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from farlog import getLogger
from tqdm import tqdm

from funresource.db.base import Resource
from funresource.generator.base import BaseGenerate

logger = getLogger("funresource")


def _get_value(entry: Tag, texts: list[str], key: str) -> str:
    for index, text in enumerate(texts):
        if "：" in text and text.split("：", 1)[0] == key:
            return text.split("：", 1)[1] or texts[index + 1]
    fallback = entry.find("b")
    if fallback is None:
        raise ValueError(f"缺少字段：{key}")
    return fallback.text


class TelegramResource(TypedDict):
    """从 Telegram 页面解析出的资源字段。"""

    name: str
    link: str
    size: str
    time: datetime


class TelegramPage:
    """Telegram 频道公开网页及其资源解析结果。"""

    def __init__(self, url: str) -> None:
        """请求指定频道页面，并解析为 HTML 文档。"""
        if url.startswith("/s"):
            url = f"https://t.me{url}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"请求 Telegram 页面失败：{url}") from exc
        self.text = response.text
        self.soup = BeautifulSoup(self.text, "lxml")

    def _page_link(self, rel: str) -> str | None:
        link = self.soup.find(rel=rel)
        href = link.get("href") if isinstance(link, Tag) else None
        return href if isinstance(href, str) else None

    def prev(self) -> str | None:
        """返回上一页链接；不存在时返回 None。"""
        return self._page_link("prev")

    def next(self) -> str | None:
        """返回下一页链接；不存在时返回 None。"""
        return self._page_link("next")

    def size(self) -> int:
        """返回当前页面资源数量。"""
        return len(self.resource())

    def resource(self) -> list[Tag]:
        """返回当前页面资源节点。"""
        return self.soup.find_all("div", {"class": "tgme_widget_message_text"})

    def parse(self) -> list[TelegramResource]:
        """解析当前页面中的资源字段。"""
        result: list[TelegramResource] = []
        for entry in self.resource():
            try:
                texts = entry.get_text("\n", strip=True).split("\n")
                time = self.soup.find("time")
                time = (
                    datetime.fromisoformat(time["datetime"])
                    if isinstance(time, Tag) and time.has_attr("datetime")
                    else datetime.now()
                )
                link = _get_value(entry, texts, "链接")
                if link and not link.startswith("https://t.me"):
                    result.append(
                        {
                            "name": _get_value(entry, texts, "名称"),
                            "link": link,
                            "size": _get_value(entry, texts, "大小"),
                            "time": time,
                        }
                    )
            except (KeyError, IndexError, AttributeError, TypeError, ValueError) as exc:
                logger.warning(
                    "跳过 Telegram 无效条目，内容={}：{}",
                    entry.get_text(" ", strip=True)[:80],
                    exc,
                )
        return result


class TelegramChannelGenerate(BaseGenerate):
    """遍历 Telegram 频道页面并生成网盘资源。"""

    def __init__(self) -> None:
        """创建采集器并载入默认频道列表。"""
        super().__init__()
        self.channel_list: list[str] = [
            "Aliyun_4K_Movies",
            "yunpanpan",
            "Q66Share",
            "shareAliyun",
            "zaihuayun",
            "Alicloud_ali",
            "share_aliyun",
            "yunpanshare",
            "Quark_Movies",
            "kuakeyun",
        ]

    def init(self) -> None:
        """Telegram 采集无需额外初始化。"""

    def load(self) -> None:
        """Telegram 页面在生成阶段按需加载。"""

    def parse_page(
        self,
        channel_name: str = "Aliyun_4K_Movies",
        page_no: int = 10,
        prefix: str = "",
    ) -> Iterator[TelegramResource]:
        """从频道首页开始，沿上一页链接最多解析指定页数。"""
        page: TelegramPage | None = None
        for _ in tqdm(range(page_no), desc=f"{prefix}-{channel_name}"):
            url = f"/s/{channel_name}" if page is None else page.prev()
            if url is None:
                break
            page = TelegramPage(url)
            yield from page.parse()

    def generate(self) -> Iterator[Resource]:
        """遍历默认频道并生成资源记录。"""
        for i, channel_name in enumerate(self.channel_list):
            for entry in self.parse_page(
                channel_name, prefix=f"{i + 1}/{len(self.channel_list)}"
            ):
                yield Resource(
                    name=entry["name"],
                    url=entry["link"],
                    update_time=entry["time"],
                )

    def destroy(self) -> None:
        """Telegram 采集无需清理临时资源。"""
