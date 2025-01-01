import os
from typing import Iterator

import pandas as pd
from funbuild.shell import run_shell
from funutil import getLogger
from tqdm import tqdm

from funresource.db.base import Resource

from .base import BaseGenerate

logger = getLogger("funresource")


class AcoooderGenerate(BaseGenerate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = pd.DataFrame()
        self.tmp_path = os.path.abspath("./funresource/tmp")

    def init(self, *args, **kwargs):
        logger.info(f"tmp path: {self.tmp_path}")
        os.makedirs(self.tmp_path, exist_ok=True)
        run_shell(
            f"git clone https://github.com/acoooder/aliyunpanshare.git {self.tmp_path}/aliyunpanshare"
        )

    def read_data(self, filepath, *args, **kwargs):
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

    def load(self, *args, **kwargs):
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
            except Exception as e:
                logger.error(f"get data from {filepath} error: {e}")
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

    def generate(self, *args, **kwargs) -> Iterator[Resource]:
        self.data.fillna("", inplace=True)
        for index, row in tqdm(self.data.iterrows(), total=len(self.data)):
            yield Resource(
                name=row["资源名称"].strip(),
                url=row["分享链接"].strip(),
                update_time=row["更新时间"],
                tags=row["资源类型"].strip(),
            )

    def destroy(self, *args, **kwargs):
        run_shell(f"rm -rf {self.tmp_path}")
