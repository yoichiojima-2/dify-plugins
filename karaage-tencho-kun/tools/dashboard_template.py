# ダッシュボードテンプレート取得ツール
# Returns inline HTML/CSS templates for Dify chat bubble rendering.
# Templates use placeholders that the LLM fills with actual data.

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

_TEMPLATES_FILE = Path(__file__).resolve().parent.parent / "data" / "dashboard_templates.json"
_TEMPLATES_CACHE: dict[str, Any] | None = None


def _load_templates() -> dict[str, Any]:
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is None:
        _TEMPLATES_CACHE = json.loads(_TEMPLATES_FILE.read_text(encoding="utf-8"))
    return _TEMPLATES_CACHE


class DashboardTemplateTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        template_type = tool_parameters.get("template_type", "").strip()
        templates_data = _load_templates()
        templates = templates_data["templates"]

        if not template_type:
            yield self.create_json_message(
                {
                    "error": "template_type が指定されていません",
                    "available_types": list(templates.keys()),
                }
            )
            return

        if template_type not in templates:
            yield self.create_json_message(
                {
                    "error": f"不明なテンプレートタイプ: {template_type}",
                    "available_types": list(templates.keys()),
                }
            )
            return

        template_info = templates[template_type]

        yield self.create_json_message(
            {
                "template_type": template_type,
                "html_template": template_info["html_template"],
                "placeholders": template_info["placeholders"],
                "instructions": template_info["instructions"],
                "constraints": templates_data["constraints"],
            }
        )
