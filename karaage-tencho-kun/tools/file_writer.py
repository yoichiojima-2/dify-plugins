# ファイル出力ツール
# Stores files in memory and returns download links via plugin endpoint

from collections.abc import Generator

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from data.file_store import store_file


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

        # Store file in memory for endpoint download
        file_id = store_file(
            content=content.encode("utf-8"),
            filename=filename,
            mime_type=mime_type,
        )

        # Try to construct download URL from credentials
        base_url = self.runtime.credentials.get("dify_base_url", "").strip().rstrip("/")
        hook_id = self.runtime.credentials.get("endpoint_hook_id", "").strip()

        if base_url and hook_id:
            download_url = f"{base_url}/e/{hook_id}/download/{file_id}"
            # Return markdown link in text message (survives Agent node)
            yield self.create_text_message(
                f"ファイル「{filename}」を作成しました。\n\n"
                f"[📥 ダウンロード: {filename}]({download_url})"
            )
        else:
            # Fallback: return blob message (works in non-agent contexts like standalone Tool nodes)
            yield self.create_blob_message(
                blob=content.encode("utf-8"),
                meta={
                    "mime_type": mime_type,
                    "filename": filename,
                },
            )
            yield self.create_text_message(
                f"ファイル「{filename}」を作成しました。上のファイルアイコンからダウンロードできます。\n\n"
                f"（ダウンロードリンクを有効にするには、プラグイン設定で Dify Base URL と Endpoint Hook ID を設定してください。）"
            )
