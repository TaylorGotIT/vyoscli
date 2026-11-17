import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "package" / "vyoscli" / "files" / "usr" / "lib"))

from vyoscli import __version__  # noqa: E402


class VersionTest(unittest.TestCase):
    def test_version_matches_makefile(self):
        text = (ROOT / "package" / "vyoscli" / "Makefile").read_text(
            encoding="utf-8")
        m = re.search(r"^PKG_VERSION:=(\S+)$", text, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(__version__, m.group(1))
