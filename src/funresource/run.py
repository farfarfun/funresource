from typing import List

from funresource.db.base import ResourceManage
from funresource.generator import RSSGenerate, TelegramChannelGenerate
from funresource.generator.base import BaseGenerate

manage = ResourceManage()
generator_list: List[BaseGenerate] = [RSSGenerate(), TelegramChannelGenerate()]

for generator in generator_list:
    manage.add_resources(generator=generator.generate())
