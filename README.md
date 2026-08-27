# funresource

网盘资源采集与管理工具：从多个来源（Acoooder、RSS 订阅、Telegram 频道）抓取网盘分享链接（阿里云盘、夸克网盘等），自动打标签（电视剧/电影/纪录片/小说等）后存入数据库，供后续检索使用。

## 安装

```bash
pip install funresource
```

## 命令行用法

```bash
funresource run
```

会依次运行内置的采集器（`AcoooderGenerate`、`RSSGenerate`、`TelegramChannelGenerate`），把抓到的资源 upsert 进数据库。

## 作为库使用

```python
from funresource.db.base import ResourceManage

manage = ResourceManage()  # 默认使用本地 sqlite，可通过 funsecret 配置 "funresource"/"engine"/"uri" 指向 MySQL 等
results = manage.find("庆余年")  # 按名称正则检索已入库的资源
```

自定义采集来源可以继承 `funresource.generator.base.BaseGenerate`，实现 `generate()` 返回 `Resource` 迭代器，再交给 `ResourceManage.add_resources()` 写库。

## 数据存储

默认使用 SQLite（`./funresource/resource.db`），可通过 [funsecret](https://github.com/farfarfun/funsecret) 配置 `funresource.engine.uri` 切换为 MySQL 等数据库。
