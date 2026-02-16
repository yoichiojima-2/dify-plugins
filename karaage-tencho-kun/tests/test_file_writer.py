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


class VariableMessage:
    """Mock variable message for testing"""

    def __init__(self, variable_name: str, variable_value):
        self.variable_name = variable_name
        self.variable_value = variable_value


class TestFileWriter(unittest.TestCase):
    def _make_tool(self, preview_url=None):
        """テスト用のツールインスタンスを作成"""
        tool = object.__new__(fw.FileWriterTool)
        tool.create_json_message = lambda body: body
        tool.create_blob_message = lambda blob, meta: BlobMessage(blob, meta)
        tool.create_text_message = lambda text: TextMessage(text)
        tool.create_variable_message = lambda name, value: VariableMessage(name, value)

        # Mock session with file upload
        tool.session = MagicMock()
        tool.session.file.upload.return_value = MagicMock(
            id="fake-file-id",
            name="output.html",
            preview_url=preview_url,
        )

        return tool

    def test_returns_error_when_content_is_empty(self) -> None:
        tool = self._make_tool()
        messages = list(tool._invoke({"content": ""}))

        self.assertEqual(len(messages), 1)
        self.assertIn("error", messages[0])

    def test_returns_blob_variable_and_text_when_preview_url_available(self) -> None:
        """When preview_url is available, returns blob + variable + text (3 messages)."""
        tool = self._make_tool(preview_url="http://api:5001/files/tools/abc.html?sign=x")
        messages = list(tool._invoke({"content": "<html></html>"}))

        self.assertEqual(len(messages), 3)  # blob + variable + text
        self.assertIsInstance(messages[0], BlobMessage)
        self.assertIsInstance(messages[1], VariableMessage)
        self.assertIsInstance(messages[2], TextMessage)

    def test_returns_blob_and_text_when_no_preview_url(self) -> None:
        """When no preview_url, returns blob + text (2 messages, no variable)."""
        tool = self._make_tool(preview_url=None)
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
        """Upload failure should not prevent blob + text from being returned."""
        tool = self._make_tool()
        tool.session.file.upload.side_effect = Exception("upload failed")

        messages = list(tool._invoke({"content": "<html></html>"}))

        # Should still return blob + text (no variable since no download_url)
        self.assertEqual(len(messages), 2)
        self.assertIsInstance(messages[0], BlobMessage)
        self.assertIsInstance(messages[1], TextMessage)

    def test_text_message_contains_filename(self) -> None:
        tool = self._make_tool()
        messages = list(
            tool._invoke({"content": "data", "filename": "report", "file_type": "csv"})
        )

        # Text message is the last message
        text_msg = [m for m in messages if isinstance(m, TextMessage)][0]
        self.assertIn("report.csv", text_msg.text)

    def test_variable_message_contains_download_link(self) -> None:
        """When upload returns preview_url, variable message should contain a markdown download link."""
        preview_url = "http://api:5001/files/tools/abc123.html?timestamp=123&nonce=xyz&sign=sig"
        tool = self._make_tool(preview_url=preview_url)
        messages = list(tool._invoke({"content": "<html></html>"}))

        var_msg = [m for m in messages if isinstance(m, VariableMessage)][0]
        self.assertEqual(var_msg.variable_name, "download_link")
        # Should contain absolute URL with http://localhost
        self.assertIn("http://localhost/files/tools/abc123.html?timestamp=123&nonce=xyz&sign=sig", var_msg.variable_value)
        # Should contain markdown link
        self.assertIn("[📎", var_msg.variable_value)
        # Should NOT contain internal Docker hostname
        self.assertNotIn("api:5001", var_msg.variable_value)
        # URL must start with http: to pass Dify frontend's isValidUrl() check
        self.assertIn("](http://localhost/", var_msg.variable_value)

    def test_no_variable_message_when_no_preview_url(self) -> None:
        """When preview_url is None, no variable message should be emitted."""
        tool = self._make_tool(preview_url=None)
        messages = list(tool._invoke({"content": "<html></html>"}))

        var_msgs = [m for m in messages if isinstance(m, VariableMessage)]
        self.assertEqual(len(var_msgs), 0)

    def test_variable_message_with_no_query_string(self) -> None:
        """preview_url without query string should still produce variable message."""
        preview_url = "http://api:5001/files/tools/abc123.html"
        tool = self._make_tool(preview_url=preview_url)
        messages = list(tool._invoke({"content": "<html></html>"}))

        var_msg = [m for m in messages if isinstance(m, VariableMessage)][0]
        self.assertIn("http://localhost/files/tools/abc123.html", var_msg.variable_value)
        self.assertNotIn("api:5001", var_msg.variable_value)

    def test_public_preview_url_used_as_is(self) -> None:
        """When preview_url has a public hostname (e.g. cloud.dify.ai), use it directly."""
        preview_url = "https://cloud.dify.ai/files/tools/abc123.html?timestamp=123&sign=sig"
        tool = self._make_tool(preview_url=preview_url)
        messages = list(tool._invoke({"content": "<html></html>"}))

        var_msg = [m for m in messages if isinstance(m, VariableMessage)][0]
        self.assertIn(preview_url, var_msg.variable_value)

    def test_dify_api_internal_host_replaced(self) -> None:
        """Internal Docker hostname 'dify-api' should be replaced with localhost."""
        preview_url = "http://dify-api:5001/files/tools/abc123.html?sign=sig"
        tool = self._make_tool(preview_url=preview_url)
        messages = list(tool._invoke({"content": "<html></html>"}))

        var_msg = [m for m in messages if isinstance(m, VariableMessage)][0]
        self.assertIn("http://localhost/files/tools/abc123.html?sign=sig", var_msg.variable_value)
        self.assertNotIn("dify-api", var_msg.variable_value)


class TestMakeDownloadUrl(unittest.TestCase):
    """Unit tests for _make_download_url helper."""

    def test_internal_api_host(self) -> None:
        url = fw._make_download_url("http://api:5001/files/tools/abc.html?sign=x")
        self.assertEqual(url, "http://localhost/files/tools/abc.html?sign=x")

    def test_internal_dify_api_host(self) -> None:
        url = fw._make_download_url("http://dify-api:5001/files/tools/abc.html")
        self.assertEqual(url, "http://localhost/files/tools/abc.html")

    def test_internal_localhost_host(self) -> None:
        url = fw._make_download_url("http://localhost:5001/files/tools/abc.html")
        self.assertEqual(url, "http://localhost/files/tools/abc.html")

    def test_public_cloud_dify_ai(self) -> None:
        url = "https://cloud.dify.ai/files/tools/abc.html?sign=x"
        self.assertEqual(fw._make_download_url(url), url)

    def test_public_custom_domain(self) -> None:
        url = "https://my-dify.example.com/files/tools/abc.html?sign=x"
        self.assertEqual(fw._make_download_url(url), url)

    def test_unknown_single_word_host_treated_as_internal(self) -> None:
        """Single-word hostnames without dots are likely Docker service names."""
        url = fw._make_download_url("http://myservice:8080/files/tools/abc.html")
        self.assertEqual(url, "http://localhost/files/tools/abc.html")


if __name__ == "__main__":
    unittest.main()
