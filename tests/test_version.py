import re
import unittest
from pathlib import Path

from agent_control_plane import __version__


class VersionMetadataTest(unittest.TestCase):
    def test_public_version_matches_package_metadata(self):
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^version = "([^"]+)"$', pyproject)
        self.assertIsNotNone(match)
        self.assertEqual(__version__, match.group(1))


if __name__ == "__main__":
    unittest.main()
