from typing import List

from funresource.db.base import ResourceManage
from funresource.generator import AcoooderGenerate, RSSGenerate, TelegramChannelGenerate
from funresource.generator.base import BaseGenerate

manage = ResourceManage()
generator_list: List[BaseGenerate] = [
    AcoooderGenerate(),
    RSSGenerate(),
    TelegramChannelGenerate(),
]

for generator in generator_list[:1]:
    manage.add_resources(generator=generator.generate())
