"""Shared helpers for the vyoscli test-suite.

The tests drive the real CLI object in-process (no shell, no router) so they
run the same way on Windows, macOS and Linux.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO_ROOT, "package", "vyoscli", "files", "usr", "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from vyoscli.cli import Cli  # noqa: E402  (import after sys.path tweak)


def new_store_dir(prefix: str = "vyoscli-test-") -> str:
    return tempfile.mkdtemp(prefix=prefix)


def new_cli(store_dir: str | None = None) -> Cli:
    """Fresh CLI bound to a throw-away config directory, in config mode."""
    directory = store_dir or new_store_dir()
    os.environ["VYOSCLI_ETC"] = directory
    os.environ["VYOSCLI_VAR_LIB"] = os.path.join(directory, "var-lib")
    os.environ["VYOSCLI_ETC_ROOT"] = os.path.join(directory, "etc")
    os.environ["VYOSCLI_SKIP_PORT_CHECK"] = "1"
    cli = Cli(directory)
    cli.ctx.mode = "cfg"
    return cli


def cfg(cli: Cli, *lines: str) -> list[str]:
    """Run config-mode lines and return one output string per line."""
    return [cli._run_cfg(shlex.split(line)) for line in lines]


def cfg_errors(cli: Cli, *lines: str) -> list[str]:
    """Run lines, returning only the outputs that look like errors."""
    bad = []
    for out in cfg(cli, *lines):
        if out.startswith(("set:", "delete:", "cfg:", "error:")):
            bad.append(out)
    return bad


def op(cli: Cli, line: str) -> str:
    return cli._run_op(shlex.split(line))


def completions(cli: Cli, line: str = "") -> list[tuple[str, str]]:
    """Completion candidates after ``line`` (empty = current node)."""
    tokens = line.split() if line.strip() else [""]
    if line.endswith(" "):
        tokens.append("")
    return cli._matches_with_help(tokens)


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
