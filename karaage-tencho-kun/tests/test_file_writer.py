import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import file_writer as fw


class BlobMessage:
    """Mock blob message for testing"""

    def __init__(self, blob: bytes, meta: dict):
        self.blob = blob
        self.meta = meta


class TestFileWriter(unittest.TestCase):
    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(fw.FileWriterTool)
        tool.create_json_message = lambda body: body
        tool.create_blob_message = lambda blob, meta: BlobMessage(blob, meta)
        return tool

    def test_returns_error_when_content_is_empty(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": ""}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_returns_blob_message(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": "<html></html>"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIsInstance(result, BlobMessage)

    def test_default_file_type_is_html(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": "<html></html>"}))
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "text/html")
        self.assertTrue(result.meta["filename"].endswith(".html"))

    def test_json_file_type(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": '{"key": "value"}', "file_type": "json"})
        )
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "application/json")
        self.assertTrue(result.meta["filename"].endswith(".json"))

    def test_csv_file_type(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "a,b,c\n1,2,3", "file_type": "csv"})
        )
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "text/csv")
        self.assertTrue(result.meta["filename"].endswith(".csv"))

    def test_txt_file_type(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "plain text", "file_type": "txt"})
        )
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "text/plain")
        self.assertTrue(result.meta["filename"].endswith(".txt"))

    def test_md_file_type(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "# Header", "file_type": "md"})
        )
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "text/markdown")
        self.assertTrue(result.meta["filename"].endswith(".md"))

    def test_custom_filename(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke(
                {"content": "<html></html>", "filename": "my_report", "file_type": "html"}
            )
        )
        result = messages[0]

        self.assertEqual(result.meta["filename"], "my_report.html")

    def test_filename_with_extension_not_duplicated(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke(
                {"content": "<html></html>", "filename": "my_report.html", "file_type": "html"}
            )
        )
        result = messages[0]

        self.assertEqual(result.meta["filename"], "my_report.html")

    def test_blob_content_is_utf8_encoded(self) -> None:
        tool = self._make_tool()
        content = "<html>日本語コンテンツ</html>"
        messages = list(tool._invoke({"content": content}))
        result = messages[0]

        self.assertEqual(result.blob, content.encode("utf-8"))

    def test_unknown_file_type_falls_back_to_plain(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "test", "file_type": "unknown"})
        )
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "text/plain")


if __name__ == "__main__":
    unittest.main()
