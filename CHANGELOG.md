# 更新日志

## 未发布

### 修复

- `pyproject.toml` 的依赖声明从 `funddb`（PyPI 上的历史快照包，传递依赖已停更的 `funlog-tau`/`funutil`）
  改为组织当前维护的 `fardb`（`fundb` 改名后的发布名，参见 farfarfun/todo-list#664），
  `src/funresource/db/base.py` 的导入路径同步从 `fundb.sqlalchemy.table` 改为 `fardb.sqlalchemy.table`。
- `pyproject.toml` 的 `description` 由占位值 `"funresource"` 改为据实描述。
- CLI 命令 `run` 移除未使用的 `*args/**kwargs`，签名改为 `run() -> None`。

## 1.0.57

### 新增

- 增加 RSS、Telegram 翻页、网络失败和坏数据边界测试。

### 修复

- 使用跨数据库 SQLAlchemy upsert，恢复默认 SQLite 写入路径。
- 统一日志入口并让 CLI 采集失败以非零状态退出。
- 修正 Telegram 下一页链接，并为外部请求增加超时和状态检查。
- 基类 `generate()` 现在返回空迭代器，与公开类型契约一致。

### 变更

- 补齐直接依赖、公开 API 类型标注和文档。

### 废弃

- 无。
