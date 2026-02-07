# からあげクン画像ツール - 感情に応じた画像を返す

import base64
from collections.abc import Generator
from pathlib import Path

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class KaraageKunImageTool(Tool):
    ASSETS_DIR = Path(__file__).parent.parent / "assets" / "karaage-kun"

    EMOTIONS = {
        "happy": ("happy.webp", "image/webp"),
        "sad": ("sad.webp", "image/webp"),
        "angry": ("angry.webp", "image/webp"),
        "idea": ("got-idea.webp", "image/webp"),
        "thinking": ("thinking.webp", "image/webp"),
        "working-hard": ("working-hard.webp", "image/webp"),
        "normal": ("normal.webp", "image/webp"),
    }

    EMOTION_LABELS = {
        "happy": "嬉しい",
        "sad": "悲しい",
        "angry": "怒り",
        "idea": "ひらめき",
        "thinking": "考え中",
        "working-hard": "頑張り中",
        "normal": "通常",
    }

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        emotion = tool_parameters.get("emotion", "normal")

        if emotion not in self.EMOTIONS:
            yield self.create_json_message({
                "error": f"Unknown emotion: {emotion}",
                "available": list(self.EMOTIONS.keys()),
            })
            return

        filename, mime_type = self.EMOTIONS[emotion]
        image_path = self.ASSETS_DIR / filename

        if not image_path.exists():
            yield self.create_json_message({"error": f"Image not found: {filename}"})
            return

        image_data = image_path.read_bytes()
        b64 = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        yield self.create_image_message(image=data_url)
