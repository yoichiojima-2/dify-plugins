"""
需要予測モデルの学習スクリプト
合成データを生成し、RandomForestで学習してモデルを保存する
"""

import json
import pickle
import random
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# 商品リスト
ITEMS = [
    "からあげクン",
    "Lチキ",
    "おにぎり",
    "サンドイッチ",
    "弁当",
    "パン",
    "冷やし麺",
    "アイスクリーム",
    "冷たい飲料",
    "温かい飲料",
    "コーヒー",
    "サラダ",
    "おでん",
    "肉まん",
    "カップ麺",
    "スイーツ",
]

# ベース需要
BASE_DEMAND = {
    "からあげクン": 80,
    "Lチキ": 40,
    "おにぎり": 150,
    "サンドイッチ": 60,
    "弁当": 70,
    "パン": 50,
    "冷やし麺": 30,
    "アイスクリーム": 40,
    "冷たい飲料": 100,
    "温かい飲料": 80,
    "コーヒー": 90,
    "サラダ": 35,
    "おでん": 50,
    "肉まん": 45,
    "カップ麺": 25,
    "スイーツ": 40,
}

# 天気・気温による需要変動ルール（合成データ生成用）
def calculate_demand(item: str, weather: str, temperature: float, humidity: float) -> int:
    """天気条件に基づいて需要を計算（合成データ生成用）"""
    base = BASE_DEMAND.get(item, 50)
    multiplier = 1.0

    # 天気による影響
    if weather == "sunny":
        if item in ["アイスクリーム", "冷たい飲料", "冷やし麺", "サラダ"]:
            multiplier *= 1.3
        elif item in ["おでん", "肉まん", "温かい飲料"]:
            multiplier *= 0.8
    elif weather == "rainy":
        if item in ["おでん", "肉まん", "カップ麺", "温かい飲料"]:
            multiplier *= 1.3
        elif item in ["アイスクリーム", "冷やし麺", "サラダ"]:
            multiplier *= 0.7
        if item in ["からあげクン", "Lチキ"]:
            multiplier *= 0.85  # 雨の日は来客減
    elif weather == "cloudy":
        multiplier *= 1.0  # 曇りは標準

    # 気温による影響
    if temperature >= 30:
        if item in ["アイスクリーム", "冷たい飲料", "冷やし麺"]:
            multiplier *= 1.0 + (temperature - 30) * 0.05
        elif item in ["おでん", "肉まん", "温かい飲料"]:
            multiplier *= 0.6
    elif temperature <= 10:
        if item in ["おでん", "肉まん", "温かい飲料", "カップ麺"]:
            multiplier *= 1.0 + (10 - temperature) * 0.05
        elif item in ["アイスクリーム", "冷たい飲料", "冷やし麺"]:
            multiplier *= 0.5
    else:
        # 20度を基準に線形補間
        temp_factor = (temperature - 20) / 20
        if item in ["アイスクリーム", "冷たい飲料", "冷やし麺"]:
            multiplier *= 1.0 + temp_factor * 0.3
        elif item in ["おでん", "肉まん", "温かい飲料"]:
            multiplier *= 1.0 - temp_factor * 0.3

    # 湿度による影響（暑い日に湿度が高いと飲料需要増）
    if temperature >= 25 and humidity >= 70:
        if item in ["冷たい飲料", "アイスクリーム"]:
            multiplier *= 1.1

    # ランダムノイズ
    noise = random.gauss(1.0, 0.15)
    multiplier *= max(0.5, min(1.5, noise))

    return max(1, int(base * multiplier))


def generate_training_data(n_samples: int = 5000) -> pd.DataFrame:
    """合成学習データを生成"""
    data = []

    weathers = ["sunny", "cloudy", "rainy"]
    weather_weights = [0.4, 0.35, 0.25]

    for _ in range(n_samples):
        weather = random.choices(weathers, weights=weather_weights)[0]

        # 季節を考慮した気温
        season = random.choice(["spring", "summer", "autumn", "winter"])
        if season == "summer":
            temperature = random.gauss(28, 4)
        elif season == "winter":
            temperature = random.gauss(8, 4)
        else:
            temperature = random.gauss(18, 5)
        temperature = max(-5, min(40, temperature))

        # 湿度
        if weather == "rainy":
            humidity = random.gauss(80, 10)
        else:
            humidity = random.gauss(60, 15)
        humidity = max(20, min(100, humidity))

        # 曜日（週末は需要増）
        day_of_week = random.randint(0, 6)
        is_weekend = 1 if day_of_week >= 5 else 0

        # 時間帯
        hour = random.randint(6, 23)

        for item in ITEMS:
            demand = calculate_demand(item, weather, temperature, humidity)

            # 週末補正
            if is_weekend:
                demand = int(demand * 1.15)

            # 時間帯補正（昼・夕方ピーク）
            if 11 <= hour <= 13 or 17 <= hour <= 19:
                demand = int(demand * 1.2)

            data.append({
                "weather": weather,
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1),
                "day_of_week": day_of_week,
                "is_weekend": is_weekend,
                "hour": hour,
                "item": item,
                "demand": demand,
            })

    return pd.DataFrame(data)


def train_model(df: pd.DataFrame) -> tuple:
    """モデルを学習"""
    # カテゴリ変数のエンコード
    weather_encoder = LabelEncoder()
    item_encoder = LabelEncoder()

    df["weather_encoded"] = weather_encoder.fit_transform(df["weather"])
    df["item_encoded"] = item_encoder.fit_transform(df["item"])

    # 特徴量とターゲット
    features = ["weather_encoded", "temperature", "humidity", "day_of_week", "is_weekend", "hour", "item_encoded"]
    X = df[features]
    y = df["demand"]

    # 学習・テスト分割
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # モデル学習（軽量化: 少ない木、浅い深さ）
    model = RandomForestRegressor(
        n_estimators=20,
        max_depth=10,
        min_samples_split=10,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 評価
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)

    print(f"Train R²: {train_score:.4f}")
    print(f"Test R²: {test_score:.4f}")

    # 特徴量重要度
    importance = dict(zip(features, model.feature_importances_))
    print("\nFeature Importance:")
    for feat, imp in sorted(importance.items(), key=lambda x: -x[1]):
        print(f"  {feat}: {imp:.4f}")

    return model, weather_encoder, item_encoder


def main():
    print("Generating training data...")
    df = generate_training_data(n_samples=3000)
    print(f"Generated {len(df)} samples")

    print("\nTraining model...")
    model, weather_encoder, item_encoder = train_model(df)

    # モデルと関連データを保存
    model_dir = Path(__file__).parent
    model_dir.mkdir(exist_ok=True)

    model_data = {
        "model": model,
        "weather_encoder": weather_encoder,
        "item_encoder": item_encoder,
        "items": ITEMS,
        "base_demand": BASE_DEMAND,
        "features": ["weather_encoded", "temperature", "humidity", "day_of_week", "is_weekend", "hour", "item_encoded"],
    }

    model_path = model_dir / "demand_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    print(f"\nModel saved to {model_path}")

    # メタデータも保存（JSONで可読性確保）
    meta = {
        "items": ITEMS,
        "weather_classes": list(weather_encoder.classes_),
        "model_type": "RandomForestRegressor",
        "n_estimators": 100,
        "features": ["weather", "temperature", "humidity", "day_of_week", "is_weekend", "hour", "item"],
    }
    meta_path = model_dir / "demand_model_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Metadata saved to {meta_path}")


if __name__ == "__main__":
    main()
