"""Argv contract for examples/runtimes/tti.py (operator TTI script)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_TTI = Path(__file__).resolve().parents[3] / "examples" / "runtimes" / "tti.py"


def _load_tti():
    if not _TTI.is_file():
        pytest.skip("examples/runtimes/tti.py is not present")
    spec = importlib.util.spec_from_file_location("tti_operator_script", _TTI)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tti():
    return _load_tti()


class TestParseArgv:
    def test_default_is_node_v(self, tti, monkeypatch):
        monkeypatch.delenv("GRAVIXLAYER_TEMPLATE", raising=False)
        n, c, template, keep, cmds = tti.parse_argv([])
        assert (n, c, template, keep) == (5, 1, "base-small", False)
        assert cmds == [("node", ["-v"])]

    def test_positional_template_without_cmds(self, tti):
        n, c, template, keep, cmds = tti.parse_argv(["10", "1", "base-medium"])
        assert (n, c, template, keep) == (10, 1, "base-medium", False)
        assert cmds == [("node", ["-v"])]

    def test_double_dash_cmds_settle_sequence(self, tti):
        n, c, template, keep, cmds = tti.parse_argv(
            ["1", "1", "base-medium", "--cmds", "true", "uname -a", "node -v", "true"]
        )
        assert (n, c, template, keep) == (1, 1, "base-medium", False)
        assert cmds == [
            ("true", []),
            ("uname", ["-a"]),
            ("node", ["-v"]),
            ("true", []),
        ]

    def test_single_dash_cmds_same_as_double(self, tti):
        n, c, template, keep, cmds = tti.parse_argv(
            ["10", "1", "base-medium", "-cmds", "true", "uname -a", "node -v", "true"]
        )
        assert (n, c, template) == (10, 1, "base-medium")
        assert cmds == [
            ("true", []),
            ("uname", ["-a"]),
            ("node", ["-v"]),
            ("true", []),
        ]

    def test_keep_aliases_and_cmds_after_keep(self, tti):
        n, c, template, keep, cmds = tti.parse_argv(
            ["3", "1", "base-medium", "-keep", "--cmds", "true", "uname -a"]
        )
        assert (n, c, template, keep) == (3, 1, "base-medium", True)
        assert cmds == [("true", []), ("uname", ["-a"])]

    def test_leftover_without_flag_is_error(self, tti):
        with pytest.raises(SystemExit, match="unexpected args"):
            tti.parse_argv(["10", "1", "base-medium", "true", "uname -a"])

    def test_cmds_flag_without_tokens_is_error(self, tti):
        with pytest.raises(SystemExit, match="needs at least one command"):
            tti.parse_argv(["1", "1", "base-medium", "--cmds"])

    def test_cmd_label(self, tti):
        assert tti.cmd_label("true", []) == "true"
        assert tti.cmd_label("node", ["-v"]) == "node -v"
        assert tti.cmd_label("uname", ["-a"]) == "uname -a"
