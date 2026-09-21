#!/usr/bin/python3


import click
from farlog import getLogger
from funresource.db.base import ResourceManage
from funresource.generator import AcoooderGenerate, RSSGenerate, TelegramChannelGenerate
from funresource.generator.base import BaseGenerate

logger = getLogger("funresource")


@click.group()
def cli() -> None:
    """资源采集命令行入口。"""


@cli.command()
def run(*args, **kwargs) -> None:
    """运行内置采集器并写入资源数据库。"""
    manage = ResourceManage()
    generator_list: list[BaseGenerate] = [
        AcoooderGenerate(),
        RSSGenerate(),
        TelegramChannelGenerate(),
    ]

    for generator in generator_list:
        try:
            generator.run(manage)
        except Exception as error:
            logger.exception("采集器 {} 执行失败", type(generator).__name__)
            raise click.ClickException(str(error)) from error


def funresource() -> None:
    """启动 funresource CLI。"""
    cli()
