# ファイル出力ツール

from collections.abc import Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._file_store import store_file


# Supported MIME types
MIME_TYPES = {
    "html": "text/html",
    "json": "application/json",
    "csv": "text/csv",
    "txt": "text/plain",
    "md": "text/markdown",
}


class FileWriterTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        content = tool_parameters.get("content", "").strip()
        filename = tool_parameters.get("filename", "output").strip()
        file_type = tool_parameters.get("file_type", "html").strip().lower()

        if not content:
            yield self.create_json_message({"error": "content is required"})
            return

        # Determine MIME type
        mime_type = MIME_TYPES.get(file_type, "text/plain")

        # Ensure filename has correct extension
        extension = f".{file_type}"
        if not filename.lower().endswith(extension):
            filename = f"{filename}{extension}"

        # HTML files: store in memory and return a clickable endpoint URL
        if file_type == "html":
            endpoint_base_url = self.runtime.credentials.get("endpoint_base_url", "").rstrip("/")
            if endpoint_base_url:
                file_id = store_file(content.encode("utf-8"))
                url = f"{endpoint_base_url}/preview/{file_id}"
                yield self.create_text_message(f"[📊 {filename}]({url})")
                return

        # Non-HTML or no endpoint configured: fall back to blob message
        yield self.create_blob_message(
            blob=content.encode("utf-8"),
            meta={
                "mime_type": mime_type,
                "filename": filename,
            },
        )
