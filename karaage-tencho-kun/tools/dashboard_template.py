"""ダッシュボードテンプレート取得ツール。

data/dashboard_templates.json からインラインHTML/CSSテンプレートを読み込み、
Difyチャットバブル内でダッシュボードを描画するためのテンプレートを返す。
テンプレートにはプレースホルダーが含まれ、LLMが実データで埋める。
"""

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.data_loader import CachedJSONLoader

_loader = CachedJSONLoader("dashboard_templates.json")

# 後方互換: テストが dt._TEMPLATES_FILE でファイルパスにアクセスする
_TEMPLATES_FILE = _loader.file_path


class DashboardTemplateTool(Tool):
    """ダッシュボードHTMLテンプレート取得ツール。

    指定されたテンプレートタイプに対応するHTML/CSSテンプレートと
    プレースホルダー情報、制約条件を返す。
    """

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        template_type = tool_parameters.get("template_type", "").strip()
        templates_data = _loader.load()
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
