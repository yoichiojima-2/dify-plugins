import sys
import unittest
from pathlib import Path
from dataclasses import dataclass

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import get_file_url as gfu


@dataclass
class MockFile:
    """Mock file object for testing"""
    filename: str
    url: str


class TestGetFileUrl(unittest.TestCase):
    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(gfu.GetFileUrlTool)
        tool.create_json_message = lambda body: body
        tool.create_text_message = lambda text: text
        return tool

    def test_returns_error_when_file_is_missing(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_returns_markdown_link_by_default(self) -> None:
        tool = self._make_tool()
        mock_file = MockFile(filename="dashboard.html", url="https://example.com/files/123.html")
        messages = list(tool._invoke({"file": mock_file}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("[📄 dashboard.html]", result)
        self.assertIn("(https://example.com/files/123.html)", result)

    def test_returns_plain_url_when_requested(self) -> None:
        tool = self._make_tool()
        mock_file = MockFile(filename="dashboard.html", url="https://example.com/files/123.html")
        messages = list(tool._invoke({"file": mock_file, "format": "plain"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertEqual(result, "https://example.com/files/123.html")

    def test_custom_link_text(self) -> None:
        tool = self._make_tool()
        mock_file = MockFile(filename="dashboard.html", url="https://example.com/files/123.html")
        messages = list(tool._invoke({"file": mock_file, "link_text": "売上ダッシュボード"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIn("[📄 売上ダッシュボード]", result)

    def test_returns_error_when_file_has_no_url(self) -> None:
        tool = self._make_tool()
        # Mock file without url attribute
        mock_file = type("MockFile", (), {"filename": "test.html"})()
        messages = list(tool._invoke({"file": mock_file}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])


if __name__ == "__main__":
    unittest.main()
