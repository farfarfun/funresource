#!/usr/bin/python3


from __future__ import annotations

import argparse
from typing import List

from funresource.db.base import ResourceManage
from funresource.generator import AcoooderGenerate, RSSGenerate, TelegramChannelGenerate
from funresource.generator.base import BaseGenerate
from funutil import getLogger

logger = getLogger("funresource")


def run(args):
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
    parser = argparse.ArgumentParser(prog="PROG")
    subparsers = parser.add_subparsers(help="sub-command help")

    # 添加子命令
    build_parser = subparsers.add_parser("run", help="build package")
    build_parser.set_defaults(func=run)  # 设置默认函数

    args = parser.parse_args()
    args.func(args)
