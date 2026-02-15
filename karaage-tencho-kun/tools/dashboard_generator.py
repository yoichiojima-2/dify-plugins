# ダッシュボード生成ツール - JSON版

from collections.abc import Generator
from datetime import datetime
from zoneinfo import ZoneInfo

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# sales_analyticsの接続を再利用
from tools.sales_analytics import _get_connection as _get_sales_connection

JST = ZoneInfo("Asia/Tokyo")


class DashboardGeneratorTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        report_type = tool_parameters.get("report_type", "daily").strip().lower()

        try:
            conn = _get_sales_connection()
            now = datetime.now(JST)

            if report_type == "daily":
                data = self._get_daily_data(conn, now)
            elif report_type == "weekly":
                data = self._get_weekly_data(conn, now)
            elif report_type == "comparison":
                data = self._get_comparison_data(conn, now)
            else:
                yield self.create_json_message(
                    {
                        "error": f"不明なレポートタイプ: {report_type}",
                        "available_types": ["daily", "weekly", "comparison"],
                    }
                )
                return

            yield self.create_json_message(data)

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _get_daily_data(self, conn, now: datetime) -> dict:
        """日次ダッシュボードデータを取得"""

        # 今日の売上データ
        today_data = conn.execute("""
            SELECT
                SUM(total_amount) as total_sales,
                SUM(quantity) as total_items,
                COUNT(DISTINCT sale_id) as transactions
            FROM sales
            WHERE sale_date = CURRENT_DATE
        """).fetchone()

        # 昨日のデータ（比較用）
        yesterday_data = conn.execute("""
            SELECT
                SUM(total_amount) as total_sales,
                SUM(quantity) as total_items
            FROM sales
            WHERE sale_date = CURRENT_DATE - 1
        """).fetchone()

        # 時間別売上
        hourly_sales = conn.execute("""
            SELECT
                sale_hour,
                SUM(total_amount) as sales
            FROM sales
            WHERE sale_date = CURRENT_DATE
            GROUP BY sale_hour
            ORDER BY sale_hour
        """).fetchall()

        # カテゴリ別売上
        category_sales = conn.execute("""
            SELECT
                category,
                SUM(total_amount) as sales
            FROM sales
            WHERE sale_date = CURRENT_DATE
            GROUP BY category
            ORDER BY sales DESC
        """).fetchall()

        total_sales = today_data[0] or 0
        total_items = today_data[1] or 0
        transactions = today_data[2] or 0
        yesterday_sales = yesterday_data[0] or 0
        yesterday_items = yesterday_data[1] or 0
        avg_transaction = total_sales // transactions if transactions > 0 else 0

        # 変化率計算
        sales_change = self._calc_change(total_sales, yesterday_sales)
        items_change = self._calc_change(total_items, yesterday_items)

        # 時間別データを整形
        hourly_data = {row[0]: row[1] for row in hourly_sales}
        hourly_breakdown = [
            {"hour": h, "sales": hourly_data.get(h, 0)}
            for h in range(6, 24)
        ]

        # カテゴリ別データを整形
        category_breakdown = [
            {"category": row[0], "sales": row[1]}
            for row in category_sales
        ]

        return {
            "report_type": "daily",
            "date": now.strftime("%Y-%m-%d"),
            "generated_at": now.isoformat(),
            "kpi": {
                "total_sales": total_sales,
                "total_items": total_items,
                "transactions": transactions,
                "avg_transaction": avg_transaction,
                "yesterday_sales": yesterday_sales,
                "yesterday_items": yesterday_items,
                "sales_change_pct": sales_change,
                "items_change_pct": items_change,
            },
            "hourly_sales": hourly_breakdown,
            "category_sales": category_breakdown,
        }

    def _get_weekly_data(self, conn, now: datetime) -> dict:
        """週次ダッシュボードデータを取得"""

        # 過去7日間の日別売上
        daily_sales = conn.execute("""
            SELECT
                sale_date,
                SUM(total_amount) as sales,
                SUM(quantity) as items
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
            AND sale_date <= CURRENT_DATE
            GROUP BY sale_date
            ORDER BY sale_date
        """).fetchall()

        # 週間合計
        week_totals = conn.execute("""
            SELECT
                SUM(total_amount) as total_sales,
                SUM(quantity) as total_items,
                COUNT(DISTINCT sale_id) as transactions
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
            AND sale_date <= CURRENT_DATE
        """).fetchone()

        # 前週データ
        prev_week = conn.execute("""
            SELECT
                SUM(total_amount) as total_sales
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 13
            AND sale_date <= CURRENT_DATE - 7
        """).fetchone()

        # カテゴリ別週間売上
        category_weekly = conn.execute("""
            SELECT
                category,
                SUM(total_amount) as sales
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
            GROUP BY category
            ORDER BY sales DESC
        """).fetchall()

        # 天気別売上
        weather_sales = conn.execute("""
            SELECT
                weather,
                SUM(total_amount) as sales,
                COUNT(DISTINCT sale_date) as days
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
            GROUP BY weather
        """).fetchall()

        total_sales = week_totals[0] or 0
        total_items = week_totals[1] or 0
        transactions = week_totals[2] or 0
        prev_sales = prev_week[0] or 0
        daily_avg = total_sales // 7 if total_sales > 0 else 0

        sales_change = self._calc_change(total_sales, prev_sales)

        # 日別データを整形
        daily_breakdown = [
            {"date": str(row[0]), "sales": row[1], "items": row[2]}
            for row in daily_sales
        ]

        # カテゴリ別データを整形
        category_breakdown = [
            {"category": row[0], "sales": row[1]}
            for row in category_weekly
        ]

        # 天気別データを整形
        weather_breakdown = [
            {"weather": row[0], "sales": row[1], "days": row[2]}
            for row in weather_sales
        ]

        return {
            "report_type": "weekly",
            "period": "過去7日間",
            "generated_at": now.isoformat(),
            "kpi": {
                "total_sales": total_sales,
                "total_items": total_items,
                "transactions": transactions,
                "daily_avg": daily_avg,
                "prev_week_sales": prev_sales,
                "sales_change_pct": sales_change,
            },
            "daily_sales": daily_breakdown,
            "category_sales": category_breakdown,
            "weather_sales": weather_breakdown,
        }

    def _get_comparison_data(self, conn, now: datetime) -> dict:
        """今週 vs 先週 比較データを取得"""

        # 今週データ（曜日別）
        this_week = conn.execute("""
            SELECT
                EXTRACT(DOW FROM sale_date) as dow,
                SUM(total_amount) as sales
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
            AND sale_date <= CURRENT_DATE
            GROUP BY EXTRACT(DOW FROM sale_date)
            ORDER BY dow
        """).fetchall()

        # 先週データ（曜日別）
        last_week = conn.execute("""
            SELECT
                EXTRACT(DOW FROM sale_date) as dow,
                SUM(total_amount) as sales
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 13
            AND sale_date <= CURRENT_DATE - 7
            GROUP BY EXTRACT(DOW FROM sale_date)
            ORDER BY dow
        """).fetchall()

        # 週間合計
        this_total = conn.execute("""
            SELECT SUM(total_amount) FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
        """).fetchone()[0] or 0

        last_total = conn.execute("""
            SELECT SUM(total_amount) FROM sales
            WHERE sale_date >= CURRENT_DATE - 13
            AND sale_date <= CURRENT_DATE - 7
        """).fetchone()[0] or 0

        # カテゴリ別比較
        this_cat = conn.execute("""
            SELECT category, SUM(total_amount) as sales
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 6
            GROUP BY category
            ORDER BY sales DESC
        """).fetchall()

        last_cat = conn.execute("""
            SELECT category, SUM(total_amount) as sales
            FROM sales
            WHERE sale_date >= CURRENT_DATE - 13
            AND sale_date <= CURRENT_DATE - 7
            GROUP BY category
            ORDER BY sales DESC
        """).fetchall()

        change_amount = this_total - last_total
        sales_change = self._calc_change(this_total, last_total)

        # 曜日別データを整形
        dow_labels = ["日", "月", "火", "水", "木", "金", "土"]
        this_week_data = {int(row[0]): row[1] for row in this_week}
        last_week_data = {int(row[0]): row[1] for row in last_week}

        dow_comparison = [
            {
                "dow": i,
                "dow_label": dow_labels[i],
                "this_week": this_week_data.get(i, 0),
                "last_week": last_week_data.get(i, 0),
            }
            for i in range(7)
        ]

        # カテゴリ別データを整形
        last_cat_dict = {row[0]: row[1] for row in last_cat}
        category_comparison = [
            {
                "category": row[0],
                "this_week": row[1],
                "last_week": last_cat_dict.get(row[0], 0),
            }
            for row in this_cat
        ]

        return {
            "report_type": "comparison",
            "period": "今週 vs 先週",
            "generated_at": now.isoformat(),
            "kpi": {
                "this_week_total": this_total,
                "last_week_total": last_total,
                "change_amount": change_amount,
                "change_pct": sales_change,
                "daily_avg_diff": change_amount // 7 if change_amount else 0,
            },
            "dow_comparison": dow_comparison,
            "category_comparison": category_comparison,
        }

    def _calc_change(self, current: float, previous: float) -> float | None:
        """変化率を計算"""
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 1)
