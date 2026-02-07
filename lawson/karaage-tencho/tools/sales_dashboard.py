# 売上ダッシュボード - HTML出力

from collections.abc import Generator
from datetime import datetime

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.sales_analytics import _get_connection


class SalesDashboardTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        try:
            conn = _get_connection()
            html = self._generate_html(conn)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")

            # プレビュー + HTMLコード
            preview = self._generate_preview(conn)

            output = f"""{preview}

---

## 📥 HTMLダッシュボードを保存

以下のHTMLをコピーして `dashboard_{timestamp}.html` として保存し、ブラウザで開いてください。

<details>
<summary>📄 HTMLコードを表示（クリックで展開）</summary>

```html
{html}
```

</details>
"""
            yield self.create_text_message(output)

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _generate_preview(self, conn: duckdb.DuckDBPyConnection) -> str:
        """チャット用のプレビュー（Markdown）"""
        total_sales = conn.execute("SELECT SUM(total_amount) FROM sales").fetchone()[0]
        total_items = conn.execute("SELECT SUM(quantity) FROM sales").fetchone()[0]
        avg_daily = conn.execute("SELECT AVG(total_sales) FROM daily_summary").fetchone()[0]

        karaage = conn.execute("""
            SELECT SUM(quantity) FROM sales WHERE item_name LIKE '%からあげクン%'
        """).fetchone()[0]

        return f"""# 🍗 からあげ店長 ダッシュボード

| 指標 | 値 |
|:-----|---:|
| 💰 総売上 | **¥{total_sales:,.0f}** |
| 📦 販売点数 | **{total_items:,}点** |
| 📈 日販平均 | **¥{avg_daily:,.0f}** |
| 🍗 からあげクン | **{karaage:,}個** |
"""

    def _generate_html(self, conn: duckdb.DuckDBPyConnection) -> str:
        """完全なHTMLダッシュボード"""
        # データ取得
        total_sales = conn.execute("SELECT SUM(total_amount) FROM sales").fetchone()[0]
        total_items = conn.execute("SELECT SUM(quantity) FROM sales").fetchone()[0]
        avg_daily = conn.execute("SELECT AVG(total_sales) FROM daily_summary").fetchone()[0]
        total_days = conn.execute("SELECT COUNT(*) FROM daily_summary").fetchone()[0]

        categories = conn.execute("""
            SELECT category, SUM(total_amount) as total
            FROM sales GROUP BY category ORDER BY total DESC
        """).fetchdf()

        karaage = conn.execute("""
            SELECT SUM(quantity), SUM(total_amount)
            FROM sales WHERE item_name LIKE '%からあげクン%'
        """).fetchone()

        weather_data = conn.execute("""
            SELECT weather, ROUND(AVG(total_sales)) as avg
            FROM daily_summary GROUP BY weather
        """).fetchdf()

        hourly = conn.execute("""
            SELECT sale_hour, SUM(total_amount) as total
            FROM sales GROUP BY sale_hour ORDER BY sale_hour
        """).fetchdf()

        top_items = conn.execute("""
            SELECT item_name, SUM(quantity) as qty, SUM(total_amount) as total
            FROM sales GROUP BY item_name ORDER BY total DESC LIMIT 5
        """).fetchdf()

        # カテゴリ別バー
        max_cat = categories["total"].max()
        cat_bars = ""
        for _, row in categories.iterrows():
            pct = (row["total"] / max_cat) * 100
            cat_bars += f'''
            <div style="display:flex;align-items:center;gap:10px;margin:8px 0;">
                <span style="width:100px;color:#94a3b8;font-size:13px;">{row["category"]}</span>
                <div style="flex:1;height:24px;background:#1e293b;border-radius:6px;overflow:hidden;">
                    <div style="width:{pct:.0f}%;height:100%;background:linear-gradient(90deg,#22d3ee,#a78bfa);border-radius:6px;"></div>
                </div>
                <span style="width:100px;text-align:right;font-weight:600;">¥{row["total"]:,.0f}</span>
            </div>'''

        # 時間帯別バー
        max_hour = hourly["total"].max()
        hour_bars = ""
        for _, row in hourly.iterrows():
            pct = (row["total"] / max_hour) * 100
            hour_bars += f'<div style="flex:1;background:linear-gradient(to top,#0891b2,#22d3ee);border-radius:4px 4px 0 0;height:{pct:.0f}%;" title="{int(row["sale_hour"])}時: ¥{row["total"]:,.0f}"></div>'

        # 天気カード
        weather_icons = {"sunny": "☀️", "cloudy": "☁️", "rainy": "🌧️"}
        weather_cards = ""
        for _, row in weather_data.iterrows():
            icon = weather_icons.get(row["weather"], "🌤️")
            weather_cards += f'''
            <div style="flex:1;text-align:center;background:#0f172a;border-radius:12px;padding:20px;">
                <div style="font-size:36px;margin-bottom:8px;">{icon}</div>
                <div style="font-size:18px;font-weight:700;">¥{row["avg"]:,.0f}</div>
                <div style="color:#64748b;font-size:12px;margin-top:4px;">日販平均</div>
            </div>'''

        # TOP5
        top_list = ""
        medals = ["🥇", "🥈", "🥉", "4", "5"]
        for i, (_, row) in enumerate(top_items.iterrows()):
            top_list += f'''
            <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #334155;">
                <span style="font-size:20px;width:32px;">{medals[i]}</span>
                <span style="flex:1;font-size:14px;">{row["item_name"]}</span>
                <span style="color:#94a3b8;font-size:13px;">{row["qty"]:,}個</span>
                <span style="font-weight:600;font-size:14px;">¥{row["total"]:,.0f}</span>
            </div>'''

        html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>からあげ店長 ダッシュボード</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans JP', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 32px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 32px;
        }}
        .logo {{ font-size: 48px; }}
        .title {{ font-size: 28px; font-weight: 800; }}
        .subtitle {{ color: #64748b; font-size: 14px; margin-top: 4px; }}
        .grid {{ display: grid; gap: 20px; }}
        .grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
        .grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
        .card {{
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 24px;
        }}
        .kpi-value {{ font-size: 32px; font-weight: 800; margin: 8px 0; }}
        .kpi-label {{ color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .cyan {{ color: #22d3ee; }}
        .purple {{ color: #a78bfa; }}
        .green {{ color: #34d399; }}
        .yellow {{ color: #fbbf24; }}
        .section-title {{ font-size: 16px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
        .hour-chart {{ display: flex; align-items: flex-end; gap: 4px; height: 120px; }}
        .weather-row {{ display: flex; gap: 16px; }}
        @media (max-width: 900px) {{
            .grid-4 {{ grid-template-columns: repeat(2, 1fr); }}
            .grid-2 {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🍗</div>
            <div>
                <div class="title">からあげ店長 ダッシュボード</div>
                <div class="subtitle">📅 過去{total_days}日間の売上分析 | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
            </div>
        </div>

        <div class="grid grid-4" style="margin-bottom:20px;">
            <div class="card">
                <div class="kpi-label">💰 総売上</div>
                <div class="kpi-value cyan">¥{total_sales:,.0f}</div>
            </div>
            <div class="card">
                <div class="kpi-label">📦 販売点数</div>
                <div class="kpi-value purple">{total_items:,}</div>
            </div>
            <div class="card">
                <div class="kpi-label">📈 日販平均</div>
                <div class="kpi-value green">¥{avg_daily:,.0f}</div>
            </div>
            <div class="card">
                <div class="kpi-label">🍗 からあげクン</div>
                <div class="kpi-value yellow">{karaage[0]:,}個</div>
            </div>
        </div>

        <div class="grid grid-2" style="margin-bottom:20px;">
            <div class="card">
                <div class="section-title">📊 カテゴリ別売上</div>
                {cat_bars}
            </div>
            <div class="card">
                <div class="section-title">⏰ 時間帯別売上</div>
                <div class="hour-chart">{hour_bars}</div>
                <div style="display:flex;justify-content:space-between;color:#64748b;font-size:11px;margin-top:8px;">
                    <span>6時</span><span>12時</span><span>18時</span><span>23時</span>
                </div>
            </div>
        </div>

        <div class="grid grid-2">
            <div class="card">
                <div class="section-title">🌤️ 天気別日販</div>
                <div class="weather-row">{weather_cards}</div>
            </div>
            <div class="card">
                <div class="section-title">🏆 売上TOP5</div>
                {top_list}
            </div>
        </div>

        <div style="text-align:center;color:#475569;font-size:12px;margin-top:32px;">
            Powered by からあげ店長 Analytics 🐔
        </div>
    </div>
</body>
</html>'''
        return html
