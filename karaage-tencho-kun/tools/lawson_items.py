"""ローソン商品カタログ検索ツール。

data/lawson_items.json からからあげクン等の商品情報を読み込み、
カテゴリ・キーワード・季節限定フラグでフィルタリングして返す。
"""

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.data_loader import CachedJSONLoader

_loader = CachedJSONLoader("lawson_items.json")


class LawsonItemsTool(Tool):
    """ローソン商品カタログ検索ツール。

    商品をカテゴリ・キーワード・季節限定フラグで絞り込んで返す。
    """

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        catalog = _loader.load()
        items = catalog["items"]
        categories = catalog["categories"]

        category = tool_parameters.get("category", "").lower().strip()
        keyword = tool_parameters.get("keyword", "").strip()
        include_seasonal = tool_parameters.get("include_seasonal", True)

        filtered_items = items.copy()

        if category:
            filtered_items = [
                item for item in filtered_items if item["category"] == category
            ]

        if keyword:
            keyword_lower = keyword.lower()
            filtered_items = [
                item
                for item in filtered_items
                if keyword_lower in item["name"].lower()
                or keyword_lower in item["name_en"].lower()
            ]

        if not include_seasonal:
            filtered_items = [
                item for item in filtered_items if not item["is_seasonal"]
            ]

        result = {
            "total_count": len(filtered_items),
            "filters_applied": {
                "category": category if category else None,
                "keyword": keyword if keyword else None,
                "include_seasonal": include_seasonal,
            },
            "categories": categories,
            "items": filtered_items,
        }

        yield self.create_json_message(result)
