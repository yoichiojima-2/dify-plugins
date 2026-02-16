# ファイル出力ツール
# Creates blob + text messages for file output.
# In chatflow mode, use standalone Tool nodes (kurokobo/file_tools) for downloads.

from collections.abc import Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

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

        mime_type = MIME_TYPES.get(file_type, "text/plain")

        extension = f".{file_type}"
        if not filename.lower().endswith(extension):
            filename = f"{filename}{extension}"

        content_bytes = content.encode("utf-8")

        yield self.create_blob_message(
            blob=content_bytes,
            meta={"mime_type": mime_type, "filename": filename},
        )

        yield self.create_text_message(
            f"ファイル「{filename}」を作成しました。"
        )
