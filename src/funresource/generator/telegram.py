from datetime import datetime
from typing import Iterator

import requests
from bs4 import BeautifulSoup
from funresource.db.base import Resource
from funresource.generator.base import BaseGenerate
from funutil import getLogger

logger = getLogger("funresource")


class TelegramPage:
    def __init__(self, url: str):
        if url.startswith("/s"):
            url = f"https://t.me{url}"
        self.text = requests.get(url).text
        self.soup = BeautifulSoup(self.text, "lxml")

    def prev(self):
        return self.soup.find(rel="prev")["href"]

    def next(self):
        return self.soup.find(rel="prev")["href"]

    def size(self):
        return len(self.resource())

    def resource(self):
        return self.soup.find_all("div", {"class": "tgme_widget_message_text"})

    def parse(self):
        result = []
        for entry in self.resource():
            try:
                texts = entry.get_text("\n", "<br>").split("\n")

                def get_value(key="名称"):
                    for i, text in enumerate(texts):
                        if "：" in text and text.split("：")[0] == key:
                            return text.split("：")[1] or texts[i + 1]
                    return entry.find("b").text

                result.append(
                    {
                        "name": get_value("名称"),
                        "link": get_value("链接"),
                        # "desc": get_value("描述"),
                        "size": get_value("大小"),
                        "time": datetime.fromisoformat(
                            self.soup.find("time")["datetime"]
                        ),
                    }
                )
            except Exception as e:
                logger.error(f"parse error: {e}")
        return result


class TelegramChannelGenerate(BaseGenerate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_list = [
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

    def init(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        pass

    def parse_page(self, channel_name="Aliyun_4K_Movies", page_no=10):
        page: TelegramPage = None
        for i in range(page_no):
            url = f"/s/{channel_name}" if page is None else page.prev()
            page = TelegramPage(url)
            for res in page.parse():
                yield res

    def generate(self, *args, **kwargs) -> Iterator[Resource]:
        for channel_name in self.channel_list:
            for entry in self.parse_page(channel_name):
                yield Resource(
                    name=entry["name"],
                    url=entry["link"],
                    update_time=entry["time"],
                )

    def destroy(self, *args, **kwargs):
        pass
