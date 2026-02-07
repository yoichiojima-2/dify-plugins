# 売上レポート生成ツール - ダウンロード可能なレポートを生成

from collections.abc import Generator
from datetime import datetime

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# sales_analyticsと同じDB接続を使用
from tools.sales_analytics import _get_connection


class SalesReportTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        report_type = tool_parameters.get("report_type", "daily")
        format_type = tool_parameters.get("format", "markdown")

        try:
            conn = _get_connection()

            if report_type == "daily":
                report = self._generate_daily_report(conn)
            elif report_type == "weekly":
                report = self._generate_weekly_report(conn)
            elif report_type == "category":
                report = self._generate_category_report(conn)
            elif report_type == "karaage":
                report = self._generate_karaage_report(conn)
            else:
                report = self._generate_daily_report(conn)

            # ファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sales_report_{report_type}_{timestamp}"

            import base64

            if format_type == "csv":
                content = self._to_csv(conn, report_type)
                mime = "text/csv"
                ext = "csv"
            else:
                content = report
                mime = "text/markdown"
                ext = "md"

            # Base64エンコードしてダウンロードリンクを生成
            b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            download_link = f"data:{mime};base64,{b64}"

            # レポート本文 + ダウンロードリンク
            output = f"""{report}

---

📥 **[レポートをダウンロード]({download_link})** ({filename}.{ext})
"""
            yield self.create_text_message(output)

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _generate_daily_report(self, conn: duckdb.DuckDBPyConnection) -> str:
        """日別売上レポート"""
        daily = conn.execute("""
            SELECT date, total_sales, total_items, weather, temperature, customer_count
            FROM daily_summary
            ORDER BY date DESC
            LIMIT 7
        """).fetchdf()

        total = conn.execute("SELECT SUM(total_sales) FROM daily_summary").fetchone()[0]
        avg_daily = conn.execute("SELECT AVG(total_sales) FROM daily_summary").fetchone()[0]

        report = f"""# 売上日報レポート
生成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## サマリ
- 期間売上合計: ¥{total:,.0f}
- 日販平均: ¥{avg_daily:,.0f}

## 直近7日間の売上

| 日付 | 売上 | 点数 | 天気 | 気温 | 客数 |
|------|------|------|------|------|------|
"""
        for _, row in daily.iterrows():
            weather_emoji = {"sunny": "☀️", "cloudy": "☁️", "rainy": "🌧️"}.get(row["weather"], "")
            report += f"| {row['date']} | ¥{row['total_sales']:,} | {row['total_items']} | {weather_emoji} | {row['temperature']}°C | {row['customer_count']} |\n"

        return report

    def _generate_weekly_report(self, conn: duckdb.DuckDBPyConnection) -> str:
        """週次分析レポート"""
        # 曜日別
        by_dow = conn.execute("""
            SELECT day_of_week,
                   ROUND(AVG(total_sales)) as avg_sales,
                   ROUND(AVG(total_items)) as avg_items
            FROM daily_summary
            GROUP BY day_of_week
            ORDER BY day_of_week
        """).fetchdf()

        dow_names = ["月", "火", "水", "木", "金", "土", "日"]

        # 時間帯別
        by_hour = conn.execute("""
            SELECT sale_hour, SUM(total_amount) as total
            FROM sales
            GROUP BY sale_hour
            ORDER BY sale_hour
        """).fetchdf()

        report = f"""# 週次分析レポート
生成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 曜日別売上傾向

| 曜日 | 平均売上 | 平均点数 |
|------|----------|----------|
"""
        for _, row in by_dow.iterrows():
            dow = dow_names[int(row["day_of_week"])]
            report += f"| {dow} | ¥{row['avg_sales']:,.0f} | {row['avg_items']:.0f} |\n"

        report += "\n## 時間帯別売上\n\n"
        report += "| 時間 | 売上 |\n|------|------|\n"
        for _, row in by_hour.iterrows():
            bar = "█" * int(row["total"] / 50000)
            report += f"| {int(row['sale_hour']):02d}:00 | ¥{row['total']:,.0f} {bar} |\n"

        return report

    def _generate_category_report(self, conn: duckdb.DuckDBPyConnection) -> str:
        """カテゴリ別レポート"""
        by_cat = conn.execute("""
            SELECT category,
                   SUM(total_amount) as total,
                   SUM(quantity) as qty,
                   ROUND(SUM(total_amount) * 100.0 / (SELECT SUM(total_amount) FROM sales), 1) as pct
            FROM sales
            GROUP BY category
            ORDER BY total DESC
        """).fetchdf()

        top_items = conn.execute("""
            SELECT item_name, SUM(quantity) as qty, SUM(total_amount) as total
            FROM sales
            GROUP BY item_name
            ORDER BY total DESC
            LIMIT 10
        """).fetchdf()

        report = f"""# カテゴリ別売上レポート
生成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## カテゴリ別売上

| カテゴリ | 売上 | 数量 | 構成比 |
|----------|------|------|--------|
"""
        for _, row in by_cat.iterrows():
            report += f"| {row['category']} | ¥{row['total']:,.0f} | {row['qty']:,} | {row['pct']}% |\n"

        report += "\n## 商品別TOP10\n\n"
        report += "| 商品名 | 数量 | 売上 |\n|--------|------|------|\n"
        for _, row in top_items.iterrows():
            report += f"| {row['item_name']} | {row['qty']:,} | ¥{row['total']:,.0f} |\n"

        return report

    def _generate_karaage_report(self, conn: duckdb.DuckDBPyConnection) -> str:
        """からあげクン専用レポート"""
        karaage = conn.execute("""
            SELECT item_name, SUM(quantity) as qty, SUM(total_amount) as total
            FROM sales
            WHERE item_name LIKE '%からあげクン%'
            GROUP BY item_name
            ORDER BY total DESC
        """).fetchdf()

        by_weather = conn.execute("""
            SELECT weather, SUM(quantity) as qty, ROUND(AVG(quantity), 1) as avg_qty
            FROM sales
            WHERE item_name LIKE '%からあげクン%'
            GROUP BY weather
        """).fetchdf()

        by_hour = conn.execute("""
            SELECT sale_hour, SUM(quantity) as qty
            FROM sales
            WHERE item_name LIKE '%からあげクン%'
            GROUP BY sale_hour
            ORDER BY sale_hour
        """).fetchdf()

        total_qty = karaage["qty"].sum()
        total_sales = karaage["total"].sum()

        report = f"""# 🐔 からあげクン売上レポート
生成日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## サマリ
- 総販売数: **{total_qty:,}個**
- 総売上: **¥{total_sales:,.0f}**

## フレーバー別

| フレーバー | 販売数 | 売上 |
|------------|--------|------|
"""
        for _, row in karaage.iterrows():
            name = row["item_name"].replace("からあげクン ", "")
            report += f"| {name} | {row['qty']:,}個 | ¥{row['total']:,.0f} |\n"

        report += "\n## 天気別販売傾向\n\n"
        report += "| 天気 | 販売数 | 平均/日 |\n|------|--------|--------|\n"
        weather_emoji = {"sunny": "☀️ 晴れ", "cloudy": "☁️ 曇り", "rainy": "🌧️ 雨"}
        for _, row in by_weather.iterrows():
            w = weather_emoji.get(row["weather"], row["weather"])
            report += f"| {w} | {row['qty']:,}個 | {row['avg_qty']}個 |\n"

        report += "\n## 時間帯別販売数\n\n```\n"
        for _, row in by_hour.iterrows():
            bar = "█" * int(row["qty"] / 20)
            report += f"{int(row['sale_hour']):02d}:00 | {bar} {row['qty']}\n"
        report += "```\n"

        return report

    def _to_csv(self, conn: duckdb.DuckDBPyConnection, report_type: str) -> str:
        """CSV形式で出力"""
        if report_type == "daily":
            df = conn.execute("""
                SELECT date, total_sales, total_items, weather, temperature, customer_count
                FROM daily_summary ORDER BY date
            """).fetchdf()
        elif report_type == "category":
            df = conn.execute("""
                SELECT category, SUM(total_amount) as total, SUM(quantity) as qty
                FROM sales GROUP BY category ORDER BY total DESC
            """).fetchdf()
        elif report_type == "karaage":
            df = conn.execute("""
                SELECT sale_date, item_name, SUM(quantity) as qty, SUM(total_amount) as total
                FROM sales WHERE item_name LIKE '%からあげクン%'
                GROUP BY sale_date, item_name ORDER BY sale_date
            """).fetchdf()
        else:
            df = conn.execute("SELECT * FROM daily_summary ORDER BY date").fetchdf()

        return df.to_csv(index=False)
