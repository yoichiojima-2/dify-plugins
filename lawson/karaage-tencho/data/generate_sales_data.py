"""売上ダミーデータを生成してCSVに保存"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# 商品マスタ
ITEMS = [
    ("K001", "からあげクン レギュラー", "ホットスナック", 238),
    ("K002", "からあげクン レッド", "ホットスナック", 238),
    ("K003", "からあげクン チーズ", "ホットスナック", 238),
    ("L001", "Lチキ", "ホットスナック", 210),
    ("L002", "Lチキ 旨辛", "ホットスナック", 210),
    ("O001", "おにぎり 鮭", "おにぎり", 140),
    ("O002", "おにぎり ツナマヨ", "おにぎり", 130),
    ("O003", "おにぎり 明太子", "おにぎり", 150),
    ("O004", "おにぎり 梅", "おにぎり", 120),
    ("B001", "幕の内弁当", "弁当", 498),
    ("B002", "のり弁当", "弁当", 398),
    ("B003", "チキン南蛮弁当", "弁当", 548),
    ("S001", "サンドイッチ たまご", "サンドイッチ", 298),
    ("S002", "サンドイッチ ハムチーズ", "サンドイッチ", 328),
    ("D001", "お茶 500ml", "飲料", 150),
    ("D002", "コーヒー 缶", "飲料", 130),
    ("D003", "スポーツドリンク", "飲料", 160),
    ("D004", "コーラ 500ml", "飲料", 170),
    ("I001", "アイスクリーム バニラ", "アイス", 180),
    ("I002", "アイスクリーム チョコ", "アイス", 180),
    ("N001", "肉まん", "中華まん", 150),
    ("N002", "ピザまん", "中華まん", 150),
    ("OD01", "おでん 大根", "おでん", 90),
    ("OD02", "おでん たまご", "おでん", 100),
    ("OD03", "おでん ちくわ", "おでん", 110),
    ("C001", "カップ麺 醤油", "カップ麺", 220),
    ("C002", "カップ麺 味噌", "カップ麺", 220),
    ("SW01", "シュークリーム", "スイーツ", 150),
    ("SW02", "プリン", "スイーツ", 180),
]

WEATHER_PATTERNS = ["sunny", "sunny", "sunny", "cloudy", "cloudy", "rainy"]


def select_item(weather: str, temperature: float, hour: int) -> tuple:
    """天気・気温・時間に基づいて商品を選択"""
    weights = []

    for item_id, name, category, price in ITEMS:
        weight = 1.0

        if weather == "sunny" and temperature > 15:
            if category == "アイス":
                weight *= 2.0
            elif category == "飲料":
                weight *= 1.5
            elif category in ["中華まん", "おでん"]:
                weight *= 0.5
        elif weather == "rainy" or temperature < 10:
            if category in ["中華まん", "おでん", "カップ麺"]:
                weight *= 2.0
            elif category == "アイス":
                weight *= 0.3

        if 7 <= hour <= 9:
            if category in ["おにぎり", "サンドイッチ", "飲料"]:
                weight *= 1.5
        elif 11 <= hour <= 13:
            if category in ["弁当", "おにぎり", "サンドイッチ"]:
                weight *= 1.8
        elif 15 <= hour <= 17:
            if category in ["スイーツ", "アイス"]:
                weight *= 1.5
        elif hour >= 20:
            if category in ["弁当", "カップ麺"]:
                weight *= 1.3

        if "からあげクン" in name:
            weight *= 1.5

        weights.append(weight)

    total_weight = sum(weights)
    r = random.uniform(0, total_weight)
    cumulative = 0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return ITEMS[i]
    return ITEMS[0]


def generate_data():
    random.seed(42)

    today = datetime(2026, 2, 7).date()  # 固定日付
    sales_data = []
    daily_data = []
    sale_id = 1

    for days_ago in range(30, -1, -1):
        date = today - timedelta(days=days_ago)
        day_of_week = date.weekday()
        is_weekend = day_of_week >= 5

        weather = random.choice(WEATHER_PATTERNS)
        base_temp = 10
        if weather == "sunny":
            temperature = base_temp + random.uniform(3, 8)
        elif weather == "rainy":
            temperature = base_temp + random.uniform(-2, 2)
        else:
            temperature = base_temp + random.uniform(0, 5)

        daily_total = 0
        daily_items = 0

        for hour in range(6, 24):
            if 7 <= hour <= 9:
                hour_weight = 1.5
            elif 11 <= hour <= 13:
                hour_weight = 2.0
            elif 17 <= hour <= 19:
                hour_weight = 1.8
            elif 21 <= hour <= 23:
                hour_weight = 0.6
            else:
                hour_weight = 1.0

            if is_weekend:
                hour_weight *= 1.2

            n_transactions = int(random.gauss(10, 3) * hour_weight)
            n_transactions = max(1, n_transactions)

            for _ in range(n_transactions):
                item_id, item_name, category, unit_price = select_item(weather, temperature, hour)
                quantity = 1 if random.random() < 0.85 else random.randint(2, 3)
                total = unit_price * quantity

                sales_data.append({
                    "sale_id": f"S{sale_id:08d}",
                    "sale_date": date.isoformat(),
                    "sale_hour": hour,
                    "item_id": item_id,
                    "item_name": item_name,
                    "category": category,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_amount": total,
                    "weather": weather,
                    "temperature": round(temperature, 1),
                    "day_of_week": day_of_week,
                })

                sale_id += 1
                daily_total += total
                daily_items += quantity

        daily_data.append({
            "date": date.isoformat(),
            "total_sales": daily_total,
            "total_items": daily_items,
            "weather": weather,
            "temperature": round(temperature, 1),
            "customer_count": int(daily_items * 0.7),
        })

    return sales_data, daily_data


def main():
    print("Generating sales data...")
    sales_data, daily_data = generate_data()

    data_dir = Path(__file__).parent

    # 商品マスタ
    items_df = pd.DataFrame(ITEMS, columns=["item_id", "item_name", "category", "unit_price"])
    items_df.to_csv(data_dir / "items.csv", index=False)
    print(f"items.csv: {len(items_df)} rows")

    # 売上データ
    sales_df = pd.DataFrame(sales_data)
    sales_df.to_csv(data_dir / "sales.csv", index=False)
    print(f"sales.csv: {len(sales_df)} rows")

    # 日別サマリ
    daily_df = pd.DataFrame(daily_data)
    daily_df.to_csv(data_dir / "daily_summary.csv", index=False)
    print(f"daily_summary.csv: {len(daily_df)} rows")

    print("Done!")


if __name__ == "__main__":
    main()
