"""シフト最適化ツール。

天気予報・曜日・需要予測を考慮して、最適なシフト配置を提案するDifyツール。
マネージャーの優先配置、からあげスキル保持者のピーク時間配置、
人件費最適化モードなどのロジックを含む。
"""

from collections.abc import Generator
from datetime import datetime

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.datetime_utils import JST, WEEKDAY_JA, WEEKDAY_KEYS
# shift_managerの接続を再利用
from tools.shift_manager import _get_connection as _get_shift_connection

# 時間帯別の必要人数（基本）
BASE_STAFF_REQUIREMENTS = {
    "early_morning": {"hours": range(6, 9), "min_staff": 2, "label": "早朝"},
    "morning": {"hours": range(9, 11), "min_staff": 2, "label": "午前"},
    "lunch_peak": {"hours": range(11, 14), "min_staff": 3, "label": "ランチピーク"},
    "afternoon": {"hours": range(14, 17), "min_staff": 2, "label": "午後"},
    "evening_peak": {"hours": range(17, 20), "min_staff": 3, "label": "夕方ピーク"},
    "night": {"hours": range(20, 23), "min_staff": 2, "label": "夜間"},
    "late_night": {"hours": range(23, 24), "min_staff": 1, "label": "深夜"},
}

# 天気による需要影響
WEATHER_IMPACT = {
    "sunny": {"multiplier": 1.1, "hot_snack_boost": 1.2},
    "cloudy": {"multiplier": 1.0, "hot_snack_boost": 1.0},
    "rainy": {"multiplier": 0.85, "hot_snack_boost": 1.3},
    "snowy": {"multiplier": 0.7, "hot_snack_boost": 1.5},
}


def _parse_availability(availability_json: str, weekday_key: str) -> list[tuple[int, int]]:
    """スタッフの出勤可能時間帯をパースする。

    availability JSONから指定曜日のスロットを取り出し、
    (開始時, 終了時) のタプルリストとして返す。
    深夜シフト（例: 22:00-06:00）にも対応。

    Args:
        availability_json: スタッフの出勤可能時間JSON文字列
        weekday_key: 曜日キー（例: "mon", "tue"）
    """
    import json

    try:
        avail = json.loads(availability_json)
        slots = avail.get(weekday_key, [])
        result = []
        for slot in slots:
            if "-" in slot:
                start, end = slot.split("-")
                start_h = int(start.split(":")[0])
                end_h = int(end.split(":")[0])
                if end_h < start_h:  # 深夜シフト (22:00-06:00)
                    end_h += 24
                result.append((start_h, end_h))
        return result
    except Exception:
        return []


def _check_hour_coverage(start: int, end: int, hour: int) -> bool:
    """指定時間がシフトでカバーされているか判定する。

    深夜シフト（end > 24）の場合、早朝時間帯（hour < 6）を
    24加算して比較する。

    Args:
        start: シフト開始時（0〜23）
        end: シフト終了時（深夜跨ぎの場合24超）
        hour: 判定対象の時間（0〜23）
    """
    if end > 24 and hour < 6:  # 深夜シフト
        hour += 24
    return start <= hour < end


class ShiftOptimizerTool(Tool):
    """シフト最適化ツール。

    指定日の天気・曜日・既存シフトを考慮し、
    最適なスタッフ配置を提案する。人件費最適化モードでは
    必要最小限の人員配置を優先する。
    """

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        target_date = tool_parameters.get("date", "").strip()
        weather = tool_parameters.get("weather", "sunny").strip().lower()
        optimize_cost = tool_parameters.get("optimize_cost", True)

        if not target_date:
            yield self.create_json_message(
                {
                    "error": "日付が指定されていません",
                    "hint": "date パラメータに YYYY-MM-DD 形式で日付を指定してください",
                }
            )
            return

        try:
            # 日付をパース
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            weekday_idx = dt.weekday()
            weekday_key = WEEKDAY_KEYS[weekday_idx]
            weekday_ja = WEEKDAY_JA[weekday_idx]
            is_weekend = weekday_idx >= 5

            conn = _get_shift_connection()

            # スタッフ情報を取得
            staff_result = conn.execute("""
                SELECT id, name, role, hourly_rate, skills, availability
                FROM staff
            """).fetchall()

            # 既存シフトを確認
            existing_shifts = conn.execute(
                """
                SELECT staff_id, start_time, end_time
                FROM shifts
                WHERE date = ? AND status IN ('confirmed', 'pending')
                """,
                [target_date],
            ).fetchall()

            existing_staff = {s[0] for s in existing_shifts}

            # 天気による需要調整
            weather_data = WEATHER_IMPACT.get(weather, WEATHER_IMPACT["cloudy"])
            demand_multiplier = weather_data["multiplier"]

            # 週末は需要増
            if is_weekend:
                demand_multiplier *= 1.2

            # ピーク時間を計算
            peak_hours = []
            for period, config in BASE_STAFF_REQUIREMENTS.items():
                if config["min_staff"] >= 3:
                    peak_hours.extend(list(config["hours"]))

            # 各時間帯の必要人数を計算
            hourly_requirements = {}
            for hour in range(6, 24):
                base_req = 2
                for period, config in BASE_STAFF_REQUIREMENTS.items():
                    if hour in config["hours"]:
                        base_req = config["min_staff"]
                        break
                hourly_requirements[hour] = max(1, int(base_req * demand_multiplier))

            # 出勤可能なスタッフをリストアップ
            available_staff = []
            for staff in staff_result:
                staff_id, name, role, hourly_rate, skills, availability = staff
                avail_slots = _parse_availability(availability, weekday_key)
                if avail_slots:
                    skills_list = skills if isinstance(skills, list) else []
                    available_staff.append(
                        {
                            "id": staff_id,
                            "name": name,
                            "role": role,
                            "hourly_rate": hourly_rate,
                            "skills": skills_list,
                            "available_slots": avail_slots,
                            "has_karaage_skill": "からあげ" in skills_list,
                            "is_manager": role == "manager",
                            "already_assigned": staff_id in existing_staff,
                        }
                    )

            # シフト最適化ロジック
            suggested_shifts = []
            hourly_coverage = {h: [] for h in range(6, 24)}
            total_labor_cost = 0

            # 1. まずマネージャーを配置
            for staff in available_staff:
                if staff["is_manager"] and not staff["already_assigned"]:
                    for start, end in staff["available_slots"]:
                        actual_end = end if end <= 24 else end - 24
                        hours = end - start
                        cost = hours * staff["hourly_rate"]
                        total_labor_cost += cost

                        suggested_shifts.append(
                            {
                                "staff_id": staff["id"],
                                "staff_name": staff["name"],
                                "start": f"{start:02d}:00",
                                "end": f"{actual_end:02d}:00",
                                "hours": hours,
                                "hourly_rate": staff["hourly_rate"],
                                "cost": cost,
                                "reason": "マネージャー責任者配置",
                            }
                        )

                        for h in range(start, min(end, 24)):
                            hourly_coverage[h].append(staff["id"])
                        break

            # 2. からあげスキル持ちをピーク時間に配置
            for staff in sorted(
                available_staff, key=lambda s: (not s["has_karaage_skill"], s["hourly_rate"])
            ):
                if staff["already_assigned"] or staff["is_manager"]:
                    continue

                for start, end in staff["available_slots"]:
                    # ランチ・夕方ピークをカバーできるか
                    covers_peak = any(
                        _check_hour_coverage(start, end, h) for h in peak_hours
                    )

                    if covers_peak or (
                        not optimize_cost and len(suggested_shifts) < len(available_staff)
                    ):
                        actual_end = end if end <= 24 else end - 24
                        hours = min(end, 24) - start
                        cost = hours * staff["hourly_rate"]

                        # 人件費最適化モードの場合、既にカバーされている時間帯はスキップ
                        if optimize_cost:
                            needs_coverage = False
                            for h in range(start, min(end, 24)):
                                if len(hourly_coverage[h]) < hourly_requirements[h]:
                                    needs_coverage = True
                                    break
                            if not needs_coverage:
                                continue

                        total_labor_cost += cost

                        reason_parts = []
                        if staff["has_karaage_skill"] and covers_peak:
                            reason_parts.append("ランチ/夕方ピーク + からあげスキル")
                        elif covers_peak:
                            reason_parts.append("ピーク時間カバー")
                        else:
                            reason_parts.append("通常シフト")

                        suggested_shifts.append(
                            {
                                "staff_id": staff["id"],
                                "staff_name": staff["name"],
                                "start": f"{start:02d}:00",
                                "end": f"{actual_end:02d}:00",
                                "hours": hours,
                                "hourly_rate": staff["hourly_rate"],
                                "cost": cost,
                                "reason": reason_parts[0],
                            }
                        )

                        for h in range(start, min(end, 24)):
                            hourly_coverage[h].append(staff["id"])
                        break

            # カバレッジ分析
            understaffed = []
            overstaffed = []
            for h in range(6, 24):
                coverage = len(hourly_coverage[h])
                required = hourly_requirements[h]
                if coverage < required:
                    understaffed.append(
                        {
                            "hour": h,
                            "coverage": coverage,
                            "required": required,
                            "shortage": required - coverage,
                        }
                    )
                elif coverage > required + 1:
                    overstaffed.append(
                        {"hour": h, "coverage": coverage, "required": required}
                    )

            yield self.create_json_message(
                {
                    "date": target_date,
                    "weekday": weekday_ja,
                    "is_weekend": is_weekend,
                    "predicted_demand": {
                        "weather": weather,
                        "weather_impact": round(demand_multiplier, 2),
                        "peak_hours": peak_hours,
                    },
                    "suggested_shifts": suggested_shifts,
                    "coverage_analysis": {
                        "understaffed_hours": understaffed,
                        "overstaffed_hours": overstaffed,
                        "hourly_requirements": hourly_requirements,
                    },
                    "cost_summary": {
                        "estimated_labor_cost": total_labor_cost,
                        "total_hours": sum(s["hours"] for s in suggested_shifts),
                        "staff_count": len(suggested_shifts),
                    },
                    "available_staff_count": len(available_staff),
                    "existing_shifts": len(existing_shifts),
                }
            )

        except ValueError:
            yield self.create_json_message(
                {
                    "error": f"無効な日付形式: {target_date}",
                    "hint": "YYYY-MM-DD 形式で指定してください（例: 2026-02-20）",
                }
            )
        except Exception as e:
            yield self.create_json_message({"error": str(e)})
