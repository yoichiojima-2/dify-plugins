# ダッシュボード生成ツール

from collections.abc import Generator
from datetime import datetime
from zoneinfo import ZoneInfo
import html

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# sales_analyticsの接続を再利用
from tools.sales_analytics import _get_connection as _get_sales_connection

JST = ZoneInfo("Asia/Tokyo")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', 'Meiryo', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            color: #333;
            font-size: 28px;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            color: #666;
            font-size: 14px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .kpi-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .kpi-card .label {{
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .kpi-card .value {{
            color: #333;
            font-size: 28px;
            font-weight: bold;
        }}
        .kpi-card .change {{
            font-size: 12px;
            margin-top: 4px;
        }}
        .kpi-card .change.positive {{
            color: #22c55e;
        }}
        .kpi-card .change.negative {{
            color: #ef4444;
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }}
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .chart-card h3 {{
            color: #333;
            font-size: 16px;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
        }}
        .footer {{
            text-align: center;
            color: white;
            margin-top: 20px;
            font-size: 12px;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>{title}</h1>
            <p class="subtitle">生成日時: {generated_at} | 期間: {period}</p>
        </div>

        <div class="kpi-grid">
            {kpi_cards}
        </div>

        <div class="chart-grid">
            {chart_cards}
        </div>

        <div class="footer">
            からあげ店長クン - 店舗運営ダッシュボード
        </div>
    </div>

    <script>
    {chart_scripts}
    </script>
</body>
</html>"""

KPI_CARD_TEMPLATE = """
<div class="kpi-card">
    <div class="label">{label}</div>
    <div class="value">{value}</div>
    <div class="change {change_class}">{change}</div>
</div>
"""

CHART_CARD_TEMPLATE = """
<div class="chart-card">
    <h3>{title}</h3>
    <div class="chart-container">
        <canvas id="{chart_id}"></canvas>
    </div>
</div>
"""


def _format_currency(amount: int) -> str:
    """金額をフォーマット"""
    return f"¥{amount:,}"


def _format_change(current: float, previous: float) -> tuple[str, str]:
    """変化率をフォーマット"""
    if previous == 0:
        return "N/A", ""
    change = ((current - previous) / previous) * 100
    if change > 0:
        return f"+{change:.1f}%", "positive"
    elif change < 0:
        return f"{change:.1f}%", "negative"
    else:
        return "±0%", ""


class DashboardGeneratorTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        report_type = tool_parameters.get("report_type", "daily").strip().lower()

        try:
            conn = _get_sales_connection()
            now = datetime.now(JST)

            if report_type == "daily":
                dashboard = self._generate_daily_dashboard(conn, now)
            elif report_type == "weekly":
                dashboard = self._generate_weekly_dashboard(conn, now)
            elif report_type == "comparison":
                dashboard = self._generate_comparison_dashboard(conn, now)
            else:
                yield self.create_json_message(
                    {
                        "error": f"不明なレポートタイプ: {report_type}",
                        "available_types": ["daily", "weekly", "comparison"],
                    }
                )
                return

            yield self.create_json_message(
                {
                    "report_type": report_type,
                    "generated_at": now.isoformat(),
                    "html": dashboard,
                }
            )

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _generate_daily_dashboard(
        self, conn, now: datetime
    ) -> str:
        """日次ダッシュボードを生成"""

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

        # KPIカード生成
        total_sales = today_data[0] or 0
        total_items = today_data[1] or 0
        transactions = today_data[2] or 0
        yesterday_sales = yesterday_data[0] or 0
        yesterday_items = yesterday_data[1] or 0

        sales_change, sales_class = _format_change(total_sales, yesterday_sales)
        items_change, items_class = _format_change(total_items, yesterday_items)
        avg_transaction = total_sales // transactions if transactions > 0 else 0

        kpi_cards = "".join(
            [
                KPI_CARD_TEMPLATE.format(
                    label="本日の売上",
                    value=_format_currency(total_sales),
                    change=f"前日比 {sales_change}",
                    change_class=sales_class,
                ),
                KPI_CARD_TEMPLATE.format(
                    label="販売点数",
                    value=f"{total_items:,}点",
                    change=f"前日比 {items_change}",
                    change_class=items_class,
                ),
                KPI_CARD_TEMPLATE.format(
                    label="客単価",
                    value=_format_currency(avg_transaction),
                    change="",
                    change_class="",
                ),
                KPI_CARD_TEMPLATE.format(
                    label="取引件数",
                    value=f"{transactions:,}件",
                    change="",
                    change_class="",
                ),
            ]
        )

        # チャート生成
        hours = [str(h) for h in range(6, 24)]
        hourly_data = {row[0]: row[1] for row in hourly_sales}
        hourly_values = [hourly_data.get(h, 0) for h in range(6, 24)]

        cat_labels = [row[0] for row in category_sales]
        cat_values = [row[1] for row in category_sales]

        chart_cards = "".join(
            [
                CHART_CARD_TEMPLATE.format(title="時間別売上", chart_id="hourlyChart"),
                CHART_CARD_TEMPLATE.format(
                    title="カテゴリ別売上", chart_id="categoryChart"
                ),
            ]
        )

        chart_scripts = f"""
        new Chart(document.getElementById('hourlyChart'), {{
            type: 'bar',
            data: {{
                labels: {hours},
                datasets: [{{
                    label: '売上',
                    data: {hourly_values},
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{ return '¥' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});

        new Chart(document.getElementById('categoryChart'), {{
            type: 'doughnut',
            data: {{
                labels: {cat_labels},
                datasets: [{{
                    data: {cat_values},
                    backgroundColor: [
                        '#667eea', '#764ba2', '#f093fb', '#f5576c',
                        '#4facfe', '#00f2fe', '#43e97b', '#38f9d7'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'right' }}
                }}
            }}
        }});
        """

        return HTML_TEMPLATE.format(
            title="本日の売上ダッシュボード",
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period=now.strftime("%Y年%m月%d日"),
            kpi_cards=kpi_cards,
            chart_cards=chart_cards,
            chart_scripts=chart_scripts,
        )

    def _generate_weekly_dashboard(
        self, conn, now: datetime
    ) -> str:
        """週次ダッシュボードを生成"""

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

        sales_change, sales_class = _format_change(total_sales, prev_sales)
        daily_avg = total_sales // 7 if total_sales > 0 else 0

        kpi_cards = "".join(
            [
                KPI_CARD_TEMPLATE.format(
                    label="週間売上",
                    value=_format_currency(total_sales),
                    change=f"前週比 {sales_change}",
                    change_class=sales_class,
                ),
                KPI_CARD_TEMPLATE.format(
                    label="日平均売上",
                    value=_format_currency(daily_avg),
                    change="",
                    change_class="",
                ),
                KPI_CARD_TEMPLATE.format(
                    label="週間販売点数",
                    value=f"{total_items:,}点",
                    change="",
                    change_class="",
                ),
                KPI_CARD_TEMPLATE.format(
                    label="週間取引件数",
                    value=f"{transactions:,}件",
                    change="",
                    change_class="",
                ),
            ]
        )

        # 日別売上チャートデータ
        dates = [str(row[0]) for row in daily_sales]
        sales_values = [row[1] for row in daily_sales]

        cat_labels = [row[0] for row in category_weekly]
        cat_values = [row[1] for row in category_weekly]

        chart_cards = "".join(
            [
                CHART_CARD_TEMPLATE.format(title="日別売上推移", chart_id="dailyChart"),
                CHART_CARD_TEMPLATE.format(
                    title="カテゴリ別売上", chart_id="categoryChart"
                ),
            ]
        )

        chart_scripts = f"""
        new Chart(document.getElementById('dailyChart'), {{
            type: 'line',
            data: {{
                labels: {dates},
                datasets: [{{
                    label: '売上',
                    data: {sales_values},
                    borderColor: 'rgba(102, 126, 234, 1)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{ return '¥' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});

        new Chart(document.getElementById('categoryChart'), {{
            type: 'bar',
            data: {{
                labels: {cat_labels},
                datasets: [{{
                    label: '売上',
                    data: {cat_values},
                    backgroundColor: [
                        '#667eea', '#764ba2', '#f093fb', '#f5576c',
                        '#4facfe', '#00f2fe', '#43e97b', '#38f9d7'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{ return '¥' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});
        """

        return HTML_TEMPLATE.format(
            title="週間売上ダッシュボード",
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period="過去7日間",
            kpi_cards=kpi_cards,
            chart_cards=chart_cards,
            chart_scripts=chart_scripts,
        )

    def _generate_comparison_dashboard(
        self, conn, now: datetime
    ) -> str:
        """今週 vs 先週 比較ダッシュボードを生成"""

        # 今週データ
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

        # 先週データ
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
        sales_change, sales_class = _format_change(this_total, last_total)

        kpi_cards = "".join(
            [
                KPI_CARD_TEMPLATE.format(
                    label="今週売上",
                    value=_format_currency(this_total),
                    change=f"前週比 {sales_change}",
                    change_class=sales_class,
                ),
                KPI_CARD_TEMPLATE.format(
                    label="先週売上",
                    value=_format_currency(last_total),
                    change="",
                    change_class="",
                ),
                KPI_CARD_TEMPLATE.format(
                    label="差額",
                    value=_format_currency(abs(change_amount)),
                    change="増加" if change_amount >= 0 else "減少",
                    change_class="positive" if change_amount >= 0 else "negative",
                ),
                KPI_CARD_TEMPLATE.format(
                    label="日平均差",
                    value=_format_currency(abs(change_amount) // 7),
                    change="",
                    change_class="",
                ),
            ]
        )

        # 曜日別データ
        dow_labels = ["日", "月", "火", "水", "木", "金", "土"]
        this_week_data = {int(row[0]): row[1] for row in this_week}
        last_week_data = {int(row[0]): row[1] for row in last_week}
        this_values = [this_week_data.get(i, 0) for i in range(7)]
        last_values = [last_week_data.get(i, 0) for i in range(7)]

        cat_labels = [row[0] for row in this_cat]
        this_cat_values = [row[1] for row in this_cat]
        last_cat_dict = {row[0]: row[1] for row in last_cat}
        last_cat_values = [last_cat_dict.get(cat, 0) for cat in cat_labels]

        chart_cards = "".join(
            [
                CHART_CARD_TEMPLATE.format(
                    title="曜日別比較", chart_id="comparisonChart"
                ),
                CHART_CARD_TEMPLATE.format(
                    title="カテゴリ別比較", chart_id="categoryCompareChart"
                ),
            ]
        )

        chart_scripts = f"""
        new Chart(document.getElementById('comparisonChart'), {{
            type: 'bar',
            data: {{
                labels: {dow_labels},
                datasets: [
                    {{
                        label: '今週',
                        data: {this_values},
                        backgroundColor: 'rgba(102, 126, 234, 0.8)'
                    }},
                    {{
                        label: '先週',
                        data: {last_values},
                        backgroundColor: 'rgba(200, 200, 200, 0.8)'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{ return '¥' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});

        new Chart(document.getElementById('categoryCompareChart'), {{
            type: 'bar',
            data: {{
                labels: {cat_labels},
                datasets: [
                    {{
                        label: '今週',
                        data: {this_cat_values},
                        backgroundColor: 'rgba(102, 126, 234, 0.8)'
                    }},
                    {{
                        label: '先週',
                        data: {last_cat_values},
                        backgroundColor: 'rgba(200, 200, 200, 0.8)'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {{
                    x: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{ return '¥' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});
        """

        return HTML_TEMPLATE.format(
            title="週間比較ダッシュボード",
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period="今週 vs 先週",
            kpi_cards=kpi_cards,
            chart_cards=chart_cards,
            chart_scripts=chart_scripts,
        )
