# からあげクン画像ツール - 感情に応じた画像を返す

import base64
from collections.abc import Generator
from pathlib import Path

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class KaraageKunImageTool(Tool):
    """からあげクンの感情画像を返すツール"""

    ASSETS_DIR = Path(__file__).parent.parent / "assets" / "karaage-kun"

    EMOTIONS = {
        "happy": "happy.webp",
        "sad": "sad.webp",
        "angry": "angry.webp",
        "idea": "got-idea.webp",
        "thinking": "thinking.webp",
        "working-hard": "working-hard.webp",
        "normal": "normal.webp",
    }

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        emotion = tool_parameters.get("emotion", "normal")

        if emotion not in self.EMOTIONS:
            yield self.create_json_message(
                {
                    "error": f"Unknown emotion: {emotion}",
                    "available": list(self.EMOTIONS.keys()),
                }
            )
            return

        filename = self.EMOTIONS[emotion]
        image_path = self.ASSETS_DIR / filename

        if not image_path.exists():
            yield self.create_json_message({"error": f"Image not found: {filename}"})
            return

        # Return image as blob - displays in UI
        # Note: This may cause issues with subsequent LLM calls due to Dify bug
        # where blob images get incorrectly formatted in conversation history
        image_bytes = image_path.read_bytes()
        yield self.create_blob_message(
            blob=image_bytes,
            meta={"mime_type": "image/webp"},
        )
