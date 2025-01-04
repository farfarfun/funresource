#!/usr/bin/python3


from typing import List

import click
from funresource.db.base import ResourceManage
from funresource.generator import AcoooderGenerate, RSSGenerate, TelegramChannelGenerate
from funresource.generator.base import BaseGenerate
from funutil import getLogger

logger = getLogger("funresource")


@click.group()
def cli():
    pass


@cli.command()
def run(*args, **kwargs):
    manage = ResourceManage()
    generator_list: List[BaseGenerate] = [
        AcoooderGenerate(),
        RSSGenerate(),
        TelegramChannelGenerate(),
    ]

    for generator in generator_list:
        try:
            generator.run(manage)
        except Exception as e:
            print(e)


def funresource():
    cli()
