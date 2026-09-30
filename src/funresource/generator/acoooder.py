import os
from collections.abc import Iterator

import pandas as pd
from farlog import getLogger
from funshell import run_shell
from tqdm import tqdm

from funresource.db.base import Resource

from .base import BaseGenerate

logger = getLogger("funresource")


class AcoooderGenerate(BaseGenerate):
    """从 Acoooder Markdown 仓库采集网盘资源。"""

    def __init__(self) -> None:
        """创建采集器并设置本地临时目录。"""
        super().__init__()
        self.data = pd.DataFrame()
        self.tmp_path = os.path.abspath("./funresource/tmp")

    def init(self) -> None:
        """创建临时目录并克隆 Acoooder 数据仓库。"""
        logger.info(f"tmp path: {self.tmp_path}")
        os.makedirs(self.tmp_path, exist_ok=True)
        run_shell(
            f"git clone https://github.com/acoooder/aliyunpanshare.git {self.tmp_path}/aliyunpanshare"
        )

    def read_data(self, filepath: str) -> pd.DataFrame:
        """读取一个 Markdown 表格并返回规范化的数据表。"""
        df = pd.read_table(
            filepath, sep="|", header=0, index_col=1, skipinitialspace=True
        )
        df = df.dropna(axis=1, how="all").iloc[1:].reset_index()
        cols = [col.strip() for col in df.columns]
        if "更新时间" not in cols:
            cols = [col.replace("发布时间", "更新时间") for col in cols]
        df.columns = cols
        if "文件名称" in cols:
            del df["文件名称"]
        return df

    def load(self) -> None:
        """加载临时目录中的全部有效 Markdown 数据表。"""
        result = []
        for file_root, dirs, files in os.walk(self.tmp_path):
            for file in files:
                if not file.endswith(".md") or "模板" in file:
                    continue
                if "README" in file:
                    continue
                filepath = os.path.join(file_root, file)
                result.append(filepath)

        pbar = tqdm(result)
        total_size = 0
        dfs = []
        for filepath in pbar:
            try:
                df = self.read_data(filepath)
                total_size = total_size + len(df)
                pbar.set_description(f"{total_size}")
                dfs.append(df)
            except (
                KeyError,
                ValueError,
                pd.errors.ParserError,
                pd.errors.EmptyDataError,
            ) as exc:
                logger.warning("跳过无法解析的数据文件 {}：{}", filepath, exc)
        if not dfs:
            self.data = pd.DataFrame(
                columns=["资源名称", "分享链接", "更新时间", "资源类型"]
            )
            return
        res = pd.concat(dfs)
        res.drop_duplicates(inplace=True)
        res.reset_index(drop=True, inplace=True)
        res[["更新时间", "资源类型"]] = res[["更新时间", "资源类型"]].astype(str)
        df2 = res.groupby(["资源名称", "分享链接"]).agg(
            {"更新时间": "max", "资源类型": "max"}
        )
        df2.reset_index(inplace=True)
        df2.sort_values("更新时间", ascending=False, inplace=True)
        df2.reset_index(drop=True, inplace=True)
        self.data = df2

    def generate(self) -> Iterator[Resource]:
        """将已加载的数据逐条转换为资源记录。"""
        self.data.fillna("", inplace=True)
        for index, row in tqdm(self.data.iterrows(), total=len(self.data)):
            yield Resource(
                name=row["资源名称"].strip(),
                url=row["分享链接"].strip(),
                update_time=row["更新时间"],
                tags=row["资源类型"].strip(),
            )

    def destroy(self) -> None:
        """删除采集时创建的临时目录。"""
        run_shell(f"rm -rf {self.tmp_path}")
