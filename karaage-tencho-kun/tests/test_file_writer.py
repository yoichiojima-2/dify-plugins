import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import file_writer as fw
from tools import _file_store


class BlobMessage:
    """Mock blob message for testing"""

    def __init__(self, blob: bytes, meta: dict):
        self.blob = blob
        self.meta = meta


class TestFileWriter(unittest.TestCase):
    def setUp(self):
        _file_store._store.clear()

    def _make_tool(self, endpoint_base_url=""):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(fw.FileWriterTool)
        tool.create_json_message = lambda body: body
        tool.create_blob_message = lambda blob, meta: BlobMessage(blob, meta)
        tool.create_text_message = lambda text: text
        tool.runtime = MagicMock()
        tool.runtime.credentials = {"endpoint_base_url": endpoint_base_url}
        return tool

    def test_returns_error_when_content_is_empty(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": ""}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_html_with_endpoint_returns_text_link(self) -> None:
        tool = self._make_tool(endpoint_base_url="https://example.com/e/abc123")
        messages = list(tool._invoke({"content": "<html></html>"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIsInstance(result, str)
        self.assertIn("[📊 output.html]", result)
        self.assertIn("https://example.com/e/abc123/preview/", result)

    def test_html_with_endpoint_stores_content(self) -> None:
        tool = self._make_tool(endpoint_base_url="https://example.com/e/abc123")
        list(tool._invoke({"content": "<html>hello</html>"}))

        self.assertEqual(len(_file_store._store), 1)
        file_id = next(iter(_file_store._store))
        content, _ = _file_store._store[file_id]
        self.assertEqual(content, b"<html>hello</html>")

    def test_html_without_endpoint_falls_back_to_blob(self) -> None:
        tool = self._make_tool(endpoint_base_url="")
        messages = list(tool._invoke({"content": "<html></html>"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIsInstance(result, BlobMessage)

    def test_non_html_returns_blob_message(self) -> None:
        tool = self._make_tool(endpoint_base_url="https://example.com/e/abc123")
        messages = list(tool._invoke({"content": "a,b,c", "file_type": "csv"}))

        self.assertEqual(len(messages), 1)
        result = messages[0]
        self.assertIsInstance(result, BlobMessage)
        self.assertEqual(result.meta["mime_type"], "text/csv")

    def test_default_file_type_is_html(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": "<html></html>"}))
        result = messages[0]

        self.assertIsInstance(result, BlobMessage)
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

    def test_custom_filename(self) -> None:
        tool = self._make_tool(endpoint_base_url="https://example.com/e/abc")
        messages = list(
            tool._invoke(
                {"content": "<html></html>", "filename": "my_report", "file_type": "html"}
            )
        )
        result = messages[0]

        self.assertIn("[📊 my_report.html]", result)

    def test_filename_with_extension_not_duplicated(self) -> None:
        tool = self._make_tool(endpoint_base_url="https://example.com/e/abc")
        messages = list(
            tool._invoke(
                {"content": "<html></html>", "filename": "my_report.html", "file_type": "html"}
            )
        )
        result = messages[0]

        self.assertIn("[📊 my_report.html]", result)
        self.assertNotIn("my_report.html.html", result)

    def test_blob_content_is_utf8_encoded(self) -> None:
        tool = self._make_tool()
        content = '{"日本語": "value"}'
        messages = list(tool._invoke({"content": content, "file_type": "json"}))
        result = messages[0]

        self.assertEqual(result.blob, content.encode("utf-8"))

    def test_unknown_file_type_falls_back_to_plain(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "test", "file_type": "unknown"})
        )
        result = messages[0]

        self.assertEqual(result.meta["mime_type"], "text/plain")

    def test_endpoint_url_trailing_slash_stripped(self) -> None:
        tool = self._make_tool(endpoint_base_url="https://example.com/e/abc/")
        messages = list(tool._invoke({"content": "<html></html>"}))
        result = messages[0]

        self.assertNotIn("//preview/", result)
        self.assertIn("/preview/", result)


if __name__ == "__main__":
    unittest.main()
