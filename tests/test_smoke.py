"""轻量级冒烟测试套件。

目标：验证核心模块可以被正常导入、`ResourceManage` 能用真实的
sqlite（临时文件 / 内存）引擎完成基本读写操作、CLI 入口可以正常
展示帮助信息；所有会触发真实网络请求的路径都用 unittest.mock 打桩。

SQLite 和 MySQL 都通过 SQLAlchemy 会话执行写入，测试覆盖默认 SQLite 路径。
"""

import sqlite3
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from sqlalchemy import inspect


# ---------------------------------------------------------------------------
# 1. 顶层包 / 子模块导入
# ---------------------------------------------------------------------------


def test_import_top_level_package():
    import funresource

    assert funresource is not None


def test_import_public_submodules():
    import funresource.db  # noqa: F401
    import funresource.db.base  # noqa: F401
    import funresource.generator  # noqa: F401
    import funresource.generator.base  # noqa: F401
    import funresource.generator.acoooder  # noqa: F401
    import funresource.generator.rss  # noqa: F401
    import funresource.generator.telegram  # noqa: F401
    import funresource.run  # noqa: F401
    import funresource.view  # noqa: F401


def test_generator_package_exports():
    from funresource import generator

    assert generator.AcoooderGenerate is not None
    assert generator.RSSGenerate is not None
    assert generator.TelegramChannelGenerate is not None
    assert set(generator.__all__) == {
        "AcoooderGenerate",
        "RSSGenerate",
        "TelegramChannelGenerate",
    }


# ---------------------------------------------------------------------------
# 2. ResourceManage + sqlite（真实引擎，不 mock DB 调用本身）
# ---------------------------------------------------------------------------


def test_resource_manage_construct_memory_sqlite():
    from funresource.db.base import ResourceManage

    manage = ResourceManage(uri="sqlite:///:memory:")
    inspector = inspect(manage.engine)
    assert "resource" in inspector.get_table_names()


def test_resource_manage_construct_file_sqlite(tmp_path):
    from funresource.db.base import ResourceManage

    db_path = tmp_path / "resource.db"
    manage = ResourceManage(uri=f"sqlite:///{db_path}")

    assert db_path.exists()
    inspector = inspect(manage.engine)
    assert "resource" in inspector.get_table_names()

    # 用底层 sqlite3 再确认一遍表结构确实落盘了
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "resource" in tables
    finally:
        conn.close()


def test_resource_manage_get_uri_explicit():
    from funresource.db.base import ResourceManage

    assert ResourceManage.get_uri("sqlite:///:memory:") == "sqlite:///:memory:"


def test_resource_manage_find_on_empty_db():
    from funresource.db.base import ResourceManage

    manage = ResourceManage(uri="sqlite:///:memory:")
    assert manage.find("anything") == []


def test_resource_manage_add_resource_works_with_sqlite():
    from funresource.db.base import Resource, ResourceManage

    manage = ResourceManage(uri="sqlite:///:memory:")
    resource = Resource(name="test", url="https://alipan.example.com/abc")

    manage.add_resource(resource)
    assert manage.find("test")[0].url == resource.url


def test_resource_manage_add_resources_works_with_sqlite():
    from funresource.db.base import Resource, ResourceManage

    manage = ResourceManage(uri="sqlite:///:memory:")

    manage.add_resources(
        iter([Resource(name="test", url="https://alipan.example.com/abc")])
    )
    assert manage.find("test")


# ---------------------------------------------------------------------------
# 3. Resource 业务逻辑（纯逻辑，无 I/O）
# ---------------------------------------------------------------------------


def test_resource_is_avail_detects_source_from_url():
    from funresource.db.base import Resource, Source

    resource = Resource(name="demo", url="https://www.alipan.com/s/xxxx", tags="电影")
    assert resource.is_avail() is True
    assert resource.source == Source.ALIYUN


def test_resource_is_avail_detects_quark_source():
    from funresource.db.base import Resource, Source

    resource = Resource(name="demo", url="https://pan.quark.cn/s/xxxx", tags="")
    assert resource.is_avail() is True
    assert resource.source == Source.KUAKE


def test_resource_is_avail_rejects_non_http_url():
    from funresource.db.base import Resource

    # 显式传 tags="" 而不是留空：Resource.tags 的 default="" 只在写入数据库时
    # 才由 SQLAlchemy 应用，直接在内存里构造对象时 tags 仍是 None，
    # 而 is_avail() 对 tags=None 的处理会抛 TypeError（既有边界情况缺陷，
    # 不在本次冒烟测试修复范围内，这里绕开它而不是触发它）。
    resource = Resource(name="demo", url="not-a-url", tags="")
    assert resource.is_avail() is False


def test_resource_to_dict_and_repr():
    from funresource.db.base import Resource

    resource = Resource(name="demo", url="https://example.com/x")
    data = resource._to_dict()
    assert data["name"] == "demo"
    assert data["url"] == "https://example.com/x"
    assert "demo" in repr(resource)


# ---------------------------------------------------------------------------
# 4. Generator 类：只做构造 / 编排层面的冒烟测试，网络 I/O 一律打桩
# ---------------------------------------------------------------------------


def test_base_generate_default_methods_are_noop():
    from funresource.generator.base import BaseGenerate

    base = BaseGenerate()
    # 默认实现都是空操作，调用不应抛异常
    base.init()
    base.load()
    base.destroy()
    # 基类 generate() 的默认实现只有 `pass`，实际返回 None（尽管类型注解
    # 写的是 Iterator[Resource]）；这里记录真实行为而不是想当然地假设
    # 返回空迭代器。
    assert base.generate() is None


def test_base_generate_run_orchestrates_without_network():
    """`run()` 应该按 init -> load -> generate -> add_resources -> destroy
    的顺序调用；这里用 MagicMock 顶替 ResourceManage，完全不触碰真实数据库
    或网络。"""
    from funresource.generator.base import BaseGenerate

    calls = []

    class FakeGenerate(BaseGenerate):
        def init(self, *a, **kw):
            calls.append("init")

        def load(self, *a, **kw):
            calls.append("load")

        def generate(self, *a, **kw):
            calls.append("generate")
            return iter([])

        def destroy(self, *a, **kw):
            calls.append("destroy")

    fake_manage = MagicMock()
    FakeGenerate().run(manage=fake_manage)

    assert calls == ["init", "load", "generate", "destroy"]
    fake_manage.add_resources.assert_called_once()


def test_acoooder_generate_constructs_without_network():
    from funresource.generator.acoooder import AcoooderGenerate

    generator = AcoooderGenerate()
    assert generator.tmp_path.endswith("funresource/tmp")
    assert generator.data.empty


def test_rss_generate_constructs_without_network():
    from funresource.generator.rss import RSSGenerate

    generator = RSSGenerate()
    assert len(generator.url_list) > 0
    assert all(url.startswith("http") for url in generator.url_list)


def test_rss_generate_generate_uses_mocked_network():
    """generate() 里真正发请求前先打桩，避免命中真实网络。"""
    from funresource.generator.rss import RSSGenerate

    generator = RSSGenerate()
    generator.url_list = ["https://example.com/feed"]

    with patch("funresource.generator.rss.requests.get") as mock_get, patch(
        "funresource.generator.rss.feedparser.parse"
    ) as mock_parse:
        mock_get.return_value = MagicMock(text="<xml></xml>")
        mock_parse.return_value = {"entries": []}

        results = list(generator.generate())

    assert results == []
    mock_get.assert_called_once_with("https://example.com/feed")


def test_telegram_channel_generate_constructs_without_network():
    from funresource.generator.telegram import TelegramChannelGenerate

    generator = TelegramChannelGenerate()
    assert len(generator.channel_list) > 0


def test_telegram_page_uses_mocked_network():
    from funresource.generator.telegram import TelegramPage

    with patch("funresource.generator.telegram.requests.get") as mock_get:
        mock_get.return_value = MagicMock(text="<html></html>")
        page = TelegramPage("/s/some_channel")

    mock_get.assert_called_once_with("https://t.me/s/some_channel")
    assert page.resource() == []


# ---------------------------------------------------------------------------
# 5. CLI 入口
# ---------------------------------------------------------------------------


def test_cli_help_via_click_runner():
    from funresource.run import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.output


def test_cli_run_subcommand_help_via_click_runner():
    from funresource.run import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])

    assert result.exit_code == 0


def test_cli_help_via_subprocess():
    """真正走 `funresource.run:funresource` 控制台脚本入口（子进程调用），
    覆盖 `[project.scripts] funresource = "funresource.run:funresource"`。"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.argv=['funresource', '--help']; "
            "from funresource.run import funresource; funresource()",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout


# ---------------------------------------------------------------------------
# 6. 需要真实凭据 / 网络才能验证的部分，明确跳过
# ---------------------------------------------------------------------------


def test_acoooder_generate_init_requires_real_network():
    pytest.skip("需要真实凭据/网络，跳过：AcoooderGenerate.init 会执行真实 git clone")


def test_telegram_channel_generate_full_crawl_requires_real_network():
    pytest.skip("需要真实凭据/网络，跳过：TelegramChannelGenerate 完整抓取依赖 t.me 真实页面")


def test_resource_manage_default_uri_may_read_real_secret_store():
    pytest.skip(
        "需要真实凭据/网络，跳过：ResourceManage() 默认构造会尝试通过 funsecret "
        "读取真实的密钥存储（read_secret('funresource', 'engine', 'uri')）"
    )
