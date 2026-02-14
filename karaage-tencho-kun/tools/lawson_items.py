from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "lawson_items.json"
_DATA_CACHE: dict[str, Any] | None = None


def _load_catalog() -> dict[str, Any]:
    global _DATA_CACHE
    if _DATA_CACHE is None:
        _DATA_CACHE = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return _DATA_CACHE


class LawsonItemsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        catalog = _load_catalog()
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
