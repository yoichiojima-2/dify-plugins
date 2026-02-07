# テキスト→HTML変換ツール

from collections.abc import Generator
from datetime import datetime

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class HtmlExportTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        content = tool_parameters.get("content", "")
        title = tool_parameters.get("title", "レポート")
        theme = tool_parameters.get("theme", "dark")

        if not content:
            yield self.create_json_message({"error": "contentが指定されていません"})
            return

        html = self._generate_html(content, title, theme)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{title}_{timestamp}.html"

        output = f"""## 📄 HTML生成完了

ファイル名: `{filename}`

<details>
<summary>📥 HTMLコードを表示（クリックでコピー用に展開）</summary>

```html
{html}
```

</details>

**保存方法:**
1. 上のHTMLコードをコピー
2. テキストエディタに貼り付け
3. `{filename}` として保存
4. ブラウザで開く
"""
        yield self.create_text_message(output)

    def _generate_html(self, content: str, title: str, theme: str) -> str:
        # テーマ設定
        if theme == "dark":
            bg = "#0f172a"
            text = "#e2e8f0"
            card_bg = "#1e293b"
            border = "#334155"
            accent = "#22d3ee"
        else:
            bg = "#f8fafc"
            text = "#1e293b"
            card_bg = "#ffffff"
            border = "#e2e8f0"
            accent = "#0891b2"

        # Markdown風の変換（簡易）
        lines = content.split("\n")
        html_content = ""
        in_code = False
        in_list = False

        for line in lines:
            # コードブロック
            if line.strip().startswith("```"):
                if in_code:
                    html_content += "</pre>"
                    in_code = False
                else:
                    html_content += f'<pre style="background:{bg};border:1px solid {border};border-radius:8px;padding:16px;overflow-x:auto;font-size:13px;">'
                    in_code = True
                continue

            if in_code:
                html_content += line + "\n"
                continue

            # 見出し
            if line.startswith("# "):
                html_content += f'<h1 style="font-size:28px;font-weight:800;margin:24px 0 16px;border-bottom:2px solid {accent};padding-bottom:8px;">{line[2:]}</h1>'
            elif line.startswith("## "):
                html_content += f'<h2 style="font-size:22px;font-weight:700;margin:20px 0 12px;color:{accent};">{line[3:]}</h2>'
            elif line.startswith("### "):
                html_content += f'<h3 style="font-size:18px;font-weight:600;margin:16px 0 8px;">{line[4:]}</h3>'
            # リスト
            elif line.strip().startswith("- "):
                if not in_list:
                    html_content += '<ul style="margin:12px 0;padding-left:24px;">'
                    in_list = True
                html_content += f'<li style="margin:6px 0;">{line.strip()[2:]}</li>'
            # テーブル
            elif "|" in line and line.strip().startswith("|"):
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if all(c.replace("-", "").replace(":", "") == "" for c in cells):
                    continue  # セパレータ行をスキップ
                row = "".join(f'<td style="padding:10px 12px;border-bottom:1px solid {border};">{c}</td>' for c in cells)
                html_content += f'<tr>{row}</tr>'
            # 水平線
            elif line.strip() in ["---", "***", "___"]:
                if in_list:
                    html_content += "</ul>"
                    in_list = False
                html_content += f'<hr style="border:none;border-top:1px solid {border};margin:24px 0;">'
            # 引用
            elif line.strip().startswith("> "):
                html_content += f'<blockquote style="border-left:4px solid {accent};padding-left:16px;margin:16px 0;color:{text};opacity:0.8;">{line.strip()[2:]}</blockquote>'
            # 太字
            elif "**" in line:
                import re
                line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                html_content += f'<p style="margin:8px 0;line-height:1.7;">{line}</p>'
            # 通常段落
            elif line.strip():
                if in_list:
                    html_content += "</ul>"
                    in_list = False
                html_content += f'<p style="margin:8px 0;line-height:1.7;">{line}</p>'
            else:
                if in_list:
                    html_content += "</ul>"
                    in_list = False

        if in_list:
            html_content += "</ul>"

        html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans JP', sans-serif;
            background: {bg};
            color: {text};
            min-height: 100vh;
            padding: 40px 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: {card_bg};
            border: 1px solid {border};
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        th {{
            background: {bg};
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        a {{ color: {accent}; }}
        code {{
            background: {bg};
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
    <div style="text-align:center;margin-top:32px;color:{text};opacity:0.5;font-size:12px;">
        Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | からあげ店長
    </div>
</body>
</html>'''
        return html
