# ファイルURL取得ツール

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class GetFileUrlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        file = tool_parameters.get("file")
        format = tool_parameters.get("format", "markdown")
        link_text = tool_parameters.get("link_text", "")

        if not file:
            yield self.create_json_message({"error": "file is required"})
            return

        # Use filename as link text if not provided
        link_text = link_text or getattr(file, "filename", "ダウンロード")
        url = getattr(file, "url", None)

        if not url:
            yield self.create_json_message({"error": "Could not get file URL"})
            return

        # Return as markdown link or plain URL
        if format == "markdown":
            result = f"[📄 {link_text}]({url})"
        else:
            result = url

        yield self.create_text_message(result)
