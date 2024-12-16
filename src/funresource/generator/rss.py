import re
import time
from datetime import datetime
from typing import Iterator

import feedparser
import requests
from bs4 import BeautifulSoup
from funresource.db.base import Resource
from funresource.generator.base import BaseGenerate
from funutil import getLogger

logger = getLogger("funresource")


class RSSGenerate(BaseGenerate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url_list = [
            "https://rsshub.app/telegram/channel/Aliyun_4K_Movies",
            "https://rsshub.app/telegram/channel/yunpanpan",
            "https://rsshub.app/telegram/channel/shareAliyun",
            "https://rsshub.app/telegram/channel/Q66Share",
        ]

    def init(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        pass

    def generate(self, *args, **kwargs) -> Iterator[Resource]:
        for url in self.url_list:
            res = requests.get(url)
            feed = feedparser.parse(res.text)

            for entry in feed["entries"]:
                soup = BeautifulSoup(entry["summary_detail"]["value"])
                # print(soup.find('p').text)

                yield Resource(
                    name=re.split(r"描述：|资源简介：", soup.find("p").text)[0]
                    .split("名称：")[1]
                    .strip(),
                    url=soup.find("a", href=True)["href"],
                    update_time=datetime.fromtimestamp(
                        time.mktime(entry["published_parsed"])
                    ),
                )

    def destroy(self, *args, **kwargs):
        pass
