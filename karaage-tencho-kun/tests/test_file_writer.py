import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from tools import file_writer as fw


class BlobMessage:
    """Mock blob message for testing"""

    def __init__(self, blob: bytes, meta: dict):
        self.blob = blob
        self.meta = meta


class TextMessage:
    """Mock text message for testing"""

    def __init__(self, text: str):
        self.text = text


class TestFileWriter(unittest.TestCase):
    def _make_tool(self):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(fw.FileWriterTool)
        tool.create_json_message = lambda body: body
        tool.create_blob_message = lambda blob, meta: BlobMessage(blob, meta)
        tool.create_text_message = lambda text: TextMessage(text)

        # Mock session with file upload
        tool.session = MagicMock()
        tool.session.file.upload.return_value = MagicMock(
            id="fake-file-id",
            name="output.html",
            preview_url=None,
        )

        return tool

    def test_returns_error_when_content_is_empty(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": ""}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_returns_blob_and_text_messages(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": "<html></html>"}))

        self.assertEqual(len(messages), 2)  # blob + text
        self.assertIsInstance(messages[0], BlobMessage)
        self.assertIsInstance(messages[1], TextMessage)

    def test_uploads_file_to_dify_storage(self) -> None:
        tool = self._make_tool()
        list(tool._invoke({"content": "<html>test</html>"}))

        tool.session.file.upload.assert_called_once_with(
            filename="output.html",
            content=b"<html>test</html>",
            mimetype="text/html",
        )

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

    def test_still_works_when_upload_fails(self) -> None:
        """Upload failure should not prevent blob message from being returned."""
        tool = self._make_tool()
        tool.session.file.upload.side_effect = Exception("upload failed")

        messages = list(tool._invoke({"content": "<html></html>"}))

        # Should still return blob + text
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], BlobMessage)
        self.assertIsInstance(messages[1], TextMessage)

    def test_text_message_contains_filename(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "data", "filename": "report", "file_type": "csv"})
        )

        self.assertIn("report.csv", messages[1].text)


if __name__ == "__main__":
    unittest.main()
