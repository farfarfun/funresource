import traceback
from datetime import datetime
from typing import Iterator

import requests
from bs4 import BeautifulSoup
from funresource.db.base import Resource
from funresource.generator.base import BaseGenerate
from funutil import getLogger
from tqdm import tqdm

logger = getLogger("funresource")


class TelegramPage:
    def __init__(self, url: str):
        if url.startswith("/s"):
            url = f"https://t.me{url}"
        self.text = requests.get(url).text
        self.soup = BeautifulSoup(self.text, "lxml")

    def prev(self):
        try:
            return self.soup.find(rel="prev")["href"]
        except Exception as e:
            logger.error(f"cannot find prev page:{e}")
            return None

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

                time = self.soup.find("time")
                time = (
                    datetime.fromisoformat(time["datetime"])
                    if time and "datetime" in time
                    else datetime.now()
                )
                link = get_value("链接")
                if link and not link.startswith("https://t.me"):
                    result.append(
                        {
                            "name": get_value("名称"),
                            "link": link,
                            "size": get_value("大小"),
                            "time": time,
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

    def parse_page(self, channel_name="Aliyun_4K_Movies", page_no=10, prefix=""):
        page: TelegramPage = None
        for i in tqdm(range(page_no), desc=f"{prefix}-{channel_name}"):
            try:
                url = f"/s/{channel_name}" if page is None else page.prev()
                if url is None:
                    break
                page = TelegramPage(url)
                for res in page.parse():
                    yield res
            except Exception as e:
                logger.error(f"parse error: {e}:{traceback.format_exc()}")

    def generate(self, *args, **kwargs) -> Iterator[Resource]:
        for i, channel_name in enumerate(self.channel_list):
            for entry in self.parse_page(
                channel_name, prefix=f"{i + 1}/{len(self.channel_list)}"
            ):
                yield Resource(
                    name=entry["name"],
                    url=entry["link"],
                    update_time=entry["time"],
                )

    def destroy(self, *args, **kwargs):
        pass
