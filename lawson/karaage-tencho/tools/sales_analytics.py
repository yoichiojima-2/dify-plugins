# 売上分析ツール - SQL版 (インメモリDB)

from collections.abc import Generator

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

_conn = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect(":memory:")
        _init_schema(_conn)
    return _conn


class SalesAnalyticsTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        sql = tool_parameters.get("sql", "").strip()

        if not sql:
            yield self.create_json_message({"error": "SQLが指定されていません"})
            return

        try:
            conn = _get_connection()
            result = conn.execute(sql).fetchdf()
            yield self.create_json_message(result.to_dict(orient="records"))

        except Exception as e:
            yield self.create_json_message({"error": str(e)})


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """スキーマとサンプルデータを初期化"""

    # 商品マスタ
    conn.execute("""
        CREATE TABLE items (
            item_id VARCHAR PRIMARY KEY,
            item_name VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            unit_price INTEGER NOT NULL
        )
    """)

    conn.execute("""
        INSERT INTO items VALUES
        ('K001', 'からあげクン レギュラー', 'ホットスナック', 238),
        ('K002', 'からあげクン レッド', 'ホットスナック', 238),
        ('K003', 'からあげクン チーズ', 'ホットスナック', 238),
        ('L001', 'Lチキ', 'ホットスナック', 210),
        ('L002', 'Lチキ 旨辛', 'ホットスナック', 210),
        ('O001', 'おにぎり 鮭', 'おにぎり', 140),
        ('O002', 'おにぎり ツナマヨ', 'おにぎり', 130),
        ('O003', 'おにぎり 明太子', 'おにぎり', 150),
        ('O004', 'おにぎり 梅', 'おにぎり', 120),
        ('B001', '幕の内弁当', '弁当', 498),
        ('B002', 'のり弁当', '弁当', 398),
        ('B003', 'チキン南蛮弁当', '弁当', 548),
        ('S001', 'サンドイッチ たまご', 'サンドイッチ', 298),
        ('S002', 'サンドイッチ ハムチーズ', 'サンドイッチ', 328),
        ('D001', 'お茶 500ml', '飲料', 150),
        ('D002', 'コーヒー 缶', '飲料', 130),
        ('D003', 'スポーツドリンク', '飲料', 160),
        ('D004', 'コーラ 500ml', '飲料', 170),
        ('I001', 'アイスクリーム バニラ', 'アイス', 180),
        ('I002', 'アイスクリーム チョコ', 'アイス', 180),
        ('N001', '肉まん', '中華まん', 150),
        ('N002', 'ピザまん', '中華まん', 150),
        ('OD01', 'おでん 大根', 'おでん', 90),
        ('OD02', 'おでん たまご', 'おでん', 100),
        ('OD03', 'おでん ちくわ', 'おでん', 110),
        ('C001', 'カップ麺 醤油', 'カップ麺', 220),
        ('C002', 'カップ麺 味噌', 'カップ麺', 220),
        ('SW01', 'シュークリーム', 'スイーツ', 150),
        ('SW02', 'プリン', 'スイーツ', 180)
    """)

    # 売上テーブル
    conn.execute("""
        CREATE TABLE sales (
            sale_id VARCHAR,
            sale_date DATE,
            sale_hour INTEGER,
            item_id VARCHAR,
            item_name VARCHAR,
            category VARCHAR,
            quantity INTEGER,
            unit_price INTEGER,
            total_amount INTEGER,
            weather VARCHAR,
            temperature FLOAT,
            day_of_week INTEGER
        )
    """)

    # 日別サマリ
    conn.execute("""
        CREATE TABLE daily_summary (
            date DATE,
            total_sales INTEGER,
            total_items INTEGER,
            weather VARCHAR,
            temperature FLOAT,
            customer_count INTEGER
        )
    """)

    # サンプル売上データを生成（過去30日分、主要パターン）
    _generate_sample_sales(conn)


def _generate_sample_sales(conn: duckdb.DuckDBPyConnection) -> None:
    """サンプル売上データを生成（SQLで効率的に）"""

    # 日別パターン（30日分）
    daily_patterns = [
        # (日付オフセット, 天気, 気温, 曜日)
        (-30, 'rainy', 8.4, 3), (-29, 'sunny', 14.2, 4), (-28, 'sunny', 15.1, 5),
        (-27, 'sunny', 13.8, 6), (-26, 'cloudy', 11.5, 0), (-25, 'cloudy', 10.2, 1),
        (-24, 'rainy', 9.1, 2), (-23, 'sunny', 12.8, 3), (-22, 'sunny', 14.5, 4),
        (-21, 'cloudy', 11.9, 5), (-20, 'sunny', 15.3, 6), (-19, 'rainy', 8.7, 0),
        (-18, 'cloudy', 10.4, 1), (-17, 'sunny', 13.2, 2), (-16, 'sunny', 14.8, 3),
        (-15, 'rainy', 7.9, 4), (-14, 'cloudy', 9.6, 5), (-13, 'sunny', 12.1, 6),
        (-12, 'sunny', 13.7, 0), (-11, 'cloudy', 11.3, 1), (-10, 'rainy', 8.2, 2),
        (-9, 'sunny', 14.1, 3), (-8, 'sunny', 15.6, 4), (-7, 'cloudy', 12.4, 5),
        (-6, 'sunny', 13.9, 6), (-5, 'rainy', 9.3, 0), (-4, 'cloudy', 10.8, 1),
        (-3, 'sunny', 14.4, 2), (-2, 'sunny', 15.2, 3), (-1, 'cloudy', 11.7, 4),
        (0, 'sunny', 13.5, 5),
    ]

    sale_id = 1
    for offset, weather, temp, dow in daily_patterns:
        is_weekend = dow >= 5
        base_multiplier = 1.2 if is_weekend else 1.0

        # 天気による補正
        if weather == 'rainy':
            hot_snack_mult = 0.8
            cold_mult = 0.5
            warm_mult = 1.5
        elif weather == 'sunny' and temp > 12:
            hot_snack_mult = 1.2
            cold_mult = 1.3
            warm_mult = 0.8
        else:
            hot_snack_mult = 1.0
            cold_mult = 1.0
            warm_mult = 1.0

        daily_sales = 0
        daily_items = 0

        # 時間帯別に売上生成
        for hour in range(6, 24):
            # 時間帯係数
            if 7 <= hour <= 9:
                hour_mult = 1.5
            elif 11 <= hour <= 13:
                hour_mult = 2.0
            elif 17 <= hour <= 19:
                hour_mult = 1.8
            elif 21 <= hour <= 23:
                hour_mult = 0.6
            else:
                hour_mult = 1.0

            # 商品別に売上生成
            items_data = [
                ('K001', 'からあげクン レギュラー', 'ホットスナック', 238, 3, hot_snack_mult),
                ('K002', 'からあげクン レッド', 'ホットスナック', 238, 2, hot_snack_mult),
                ('K003', 'からあげクン チーズ', 'ホットスナック', 238, 2, hot_snack_mult),
                ('L001', 'Lチキ', 'ホットスナック', 210, 2, hot_snack_mult),
                ('O001', 'おにぎり 鮭', 'おにぎり', 140, 4, 1.0),
                ('O002', 'おにぎり ツナマヨ', 'おにぎり', 130, 5, 1.0),
                ('B001', '幕の内弁当', '弁当', 498, 2, 1.0),
                ('B002', 'のり弁当', '弁当', 398, 3, 1.0),
                ('S001', 'サンドイッチ たまご', 'サンドイッチ', 298, 2, 1.0),
                ('D001', 'お茶 500ml', '飲料', 150, 4, cold_mult),
                ('D002', 'コーヒー 缶', '飲料', 130, 3, 1.0),
                ('I001', 'アイスクリーム バニラ', 'アイス', 180, 1, cold_mult),
                ('N001', '肉まん', '中華まん', 150, 2, warm_mult),
                ('OD01', 'おでん 大根', 'おでん', 90, 2, warm_mult),
                ('OD02', 'おでん たまご', 'おでん', 100, 2, warm_mult),
                ('C001', 'カップ麺 醤油', 'カップ麺', 220, 1, warm_mult),
                ('SW01', 'シュークリーム', 'スイーツ', 150, 2, 1.0),
            ]

            for item_id, item_name, category, price, base_qty, cat_mult in items_data:
                qty = max(1, int(base_qty * hour_mult * base_multiplier * cat_mult * 0.3))
                total = price * qty

                conn.execute("""
                    INSERT INTO sales VALUES (?, CURRENT_DATE + ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    f"S{sale_id:08d}", offset, hour,
                    item_id, item_name, category,
                    qty, price, total,
                    weather, temp, dow
                ])

                sale_id += 1
                daily_sales += total
                daily_items += qty

        # 日別サマリ
        conn.execute("""
            INSERT INTO daily_summary VALUES (CURRENT_DATE + ?, ?, ?, ?, ?, ?)
        """, [offset, daily_sales, daily_items, weather, temp, int(daily_items * 0.7)])
