"""轻量级冒烟测试套件。

目标：验证核心模块可以被正常导入、`ResourceManage` 能用真实的
sqlite（临时文件 / 内存）引擎完成基本读写操作、CLI 入口可以正常
展示帮助信息；所有会触发真实网络请求的路径都用 unittest.mock 打桩。

SQLite 和 MySQL 都通过 SQLAlchemy 会话执行写入，测试覆盖默认 SQLite 路径。
"""

import sqlite3
import subprocess
import sys
import time
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
    import funresource.db
    import funresource.db.base
    import funresource.generator
    import funresource.generator.acoooder
    import funresource.generator.base
    import funresource.generator.rss
    import funresource.generator.telegram
    import funresource.run
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
    assert list(base.generate()) == []


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


def test_base_generate_run_cleans_up_after_failure():
    from funresource.generator.base import BaseGenerate

    generator = BaseGenerate()
    generator.load = MagicMock(side_effect=RuntimeError("failed"))
    generator.destroy = MagicMock()

    with pytest.raises(RuntimeError, match="failed"):
        generator.run(manage=MagicMock())

    generator.destroy.assert_called_once_with()


def test_acoooder_generate_constructs_without_network():
    from funresource.generator.acoooder import AcoooderGenerate

    generator = AcoooderGenerate()
    assert generator.tmp_path.endswith("funresource/tmp")
    assert generator.data.empty


def test_acoooder_load_handles_empty_directory(tmp_path):
    from funresource.generator.acoooder import AcoooderGenerate

    generator = AcoooderGenerate()
    generator.tmp_path = str(tmp_path)
    generator.load()

    assert generator.data.empty
    assert list(generator.generate()) == []


def test_acoooder_load_skips_invalid_markdown(tmp_path):
    from funresource.generator.acoooder import AcoooderGenerate

    (tmp_path / "bad.md").write_text("invalid", encoding="utf-8")
    generator = AcoooderGenerate()
    generator.tmp_path = str(tmp_path)

    with patch.object(generator, "read_data", side_effect=ValueError("bad table")):
        generator.load()

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

    with (
        patch("funresource.generator.rss.requests.get") as mock_get,
        patch("funresource.generator.rss.feedparser.parse") as mock_parse,
    ):
        mock_get.return_value = MagicMock(text="<xml></xml>")
        mock_parse.return_value = {"entries": []}

        results = list(generator.generate())

    assert results == []
    mock_get.assert_called_once_with("https://example.com/feed", timeout=10)


def test_rss_generate_parses_valid_entry_and_skips_invalid_entry():
    from funresource.generator.rss import RSSGenerate

    generator = RSSGenerate()
    generator.url_list = ["https://example.com/feed"]
    valid = {
        "summary_detail": {
            "value": '<p>名称：示例电影<br>描述：高清</p><a href="https://www.alipan.com/s/abc">链接</a>'
        },
        "published_parsed": time.gmtime(0),
    }
    response = MagicMock(text="<xml></xml>")

    with (
        patch("funresource.generator.rss.requests.get", return_value=response),
        patch(
            "funresource.generator.rss.feedparser.parse",
            return_value={"entries": [{}, valid]},
        ),
    ):
        results = list(generator.generate())

    assert len(results) == 1
    assert results[0].name == "示例电影"
    assert results[0].url == "https://www.alipan.com/s/abc"


def test_rss_generate_reports_timeout():
    import requests

    from funresource.generator.rss import RSSGenerate

    generator = RSSGenerate()
    generator.url_list = ["https://example.com/feed"]

    with (
        patch(
            "funresource.generator.rss.requests.get",
            side_effect=requests.Timeout("timed out"),
        ),
        pytest.raises(RuntimeError, match="https://example.com/feed"),
    ):
        list(generator.generate())


def test_telegram_channel_generate_constructs_without_network():
    from funresource.generator.telegram import TelegramChannelGenerate

    generator = TelegramChannelGenerate()
    assert len(generator.channel_list) > 0


def test_telegram_page_uses_mocked_network():
    from funresource.generator.telegram import TelegramPage

    with patch("funresource.generator.telegram.requests.get") as mock_get:
        mock_get.return_value = MagicMock(text="<html></html>")
        page = TelegramPage("/s/some_channel")

    mock_get.assert_called_once_with("https://t.me/s/some_channel", timeout=10)
    assert page.resource() == []


def test_telegram_page_navigation_and_resource_parsing():
    from funresource.generator.telegram import TelegramPage

    html = """
    <a rel="prev" href="/s/channel?before=1"></a>
    <a rel="next" href="/s/channel?after=1"></a>
    <time datetime="2026-09-30T12:00:00+00:00"></time>
    <div class="tgme_widget_message_text">
      <b>名称：示例电影</b><br>链接：https://www.alipan.com/s/abc<br>大小：1GB
    </div>
    """
    with patch("funresource.generator.telegram.requests.get") as mock_get:
        mock_get.return_value = MagicMock(text=html)
        page = TelegramPage("https://t.me/s/channel")

    assert page.prev() == "/s/channel?before=1"
    assert page.next() == "/s/channel?after=1"
    resources = page.parse()
    assert resources[0]["name"] == "示例电影"
    assert resources[0]["link"] == "https://www.alipan.com/s/abc"
    assert resources[0]["size"] == "1GB"
    assert resources[0]["time"].isoformat() == "2026-09-30T12:00:00+00:00"


def test_telegram_page_reports_timeout():
    import requests

    from funresource.generator.telegram import TelegramPage

    with (
        patch(
            "funresource.generator.telegram.requests.get",
            side_effect=requests.Timeout("timed out"),
        ),
        pytest.raises(RuntimeError, match="https://t.me/s/channel"),
    ):
        TelegramPage("https://t.me/s/channel")


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


def test_cli_run_returns_nonzero_when_generator_fails():
    from funresource.run import cli

    runner = CliRunner()
    with patch(
        "funresource.run.AcoooderGenerate.run", side_effect=RuntimeError("failed")
    ):
        result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0
    assert "failed" in result.output


def test_cli_help_via_subprocess():
    """真正走 `funresource.run:funresource` 控制台脚本入口（子进程调用），
    覆盖 `[project.scripts] funresource = "funresource.run:funresource"`。"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.argv=['funresource', '--help']; "
                "from funresource.run import funresource; funresource()"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout
