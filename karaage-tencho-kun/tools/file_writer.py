# ファイル出力ツール
# Uploads files to Dify's built-in storage via session.file.upload()
# Returns download link extracted from preview_url + blob message as fallback

from collections.abc import Generator
from urllib.parse import urlparse

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


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

        content_bytes = content.encode("utf-8")

        # Upload file to Dify's built-in storage and get signed download URL
        download_url = None
        try:
            upload_response = self.session.file.upload(
                filename=filename,
                content=content_bytes,
                mimetype=mime_type,
            )
            # preview_url contains a signed URL for downloading the file
            # It may use an internal Docker hostname (e.g., http://api:5001/files/tools/...)
            # Extract the path+query so the link works relative to the user's Dify domain
            if upload_response and upload_response.preview_url:
                parsed = urlparse(upload_response.preview_url)
                download_url = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
        except Exception:
            pass  # Upload failure is non-fatal; blob message still provides the file

        # Return blob message for file download (works in non-agent contexts)
        yield self.create_blob_message(
            blob=content_bytes,
            meta={
                "mime_type": mime_type,
                "filename": filename,
            },
        )

        # Return text message with download link if available
        if download_url:
            yield self.create_text_message(
                f"📥 ファイル「{filename}」を作成しました。\n\n"
                f"[📎 {filename} をダウンロード]({download_url})"
            )
        else:
            yield self.create_text_message(
                f"ファイル「{filename}」を作成しました。上のファイルアイコンからダウンロードできます。"
            )
