"""シフト表データ取得ツール。

週間・日次・スタッフ別のシフト表データをDuckDBから取得し、
JSON形式で返すDifyツール。dashboard_templateツールと組み合わせて
チャットバブル内にシフト表をインライン描画する。
"""

from collections.abc import Generator
from datetime import datetime, timedelta

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.datetime_utils import JST, WEEKDAY_JA
from tools.shift_manager import _get_connection as _get_shift_connection


class ShiftTableGeneratorTool(Tool):
    """シフト表データ取得ツール。

    ビュータイプ（weekly / daily / staff）に応じて、
    DuckDBからシフトデータを取得しJSON形式で返す。
    """

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        view_type = tool_parameters.get("view_type", "weekly").strip().lower()
        start_date = tool_parameters.get("start_date", "").strip()

        try:
            now = datetime.now(JST)

            # 開始日の決定
            if start_date:
                base_date = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                # デフォルト: 今週の月曜日
                base_date = now - timedelta(days=now.weekday())

            base_date = base_date.replace(tzinfo=JST)

            if view_type == "weekly":
                data = self._get_weekly_data(base_date, now)
            elif view_type == "daily":
                data = self._get_daily_data(base_date, now)
            elif view_type == "staff":
                data = self._get_staff_view_data(base_date, now)
            else:
                yield self.create_json_message(
                    {
                        "error": f"不明なビュータイプ: {view_type}",
                        "available_types": ["weekly", "daily", "staff"],
                    }
                )
                return

            yield self.create_json_message(data)

        except ValueError as e:
            yield self.create_json_message(
                {
                    "error": f"日付形式エラー: {e}",
                    "hint": "YYYY-MM-DD 形式で指定してください",
                }
            )
        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _get_weekly_data(self, base_date: datetime, now: datetime) -> dict:
        """週間シフトデータを取得する。

        指定された開始日から7日間のシフトデータを、
        スタッフ×日付のマトリクス形式で返す。

        Args:
            base_date: 週の開始日（月曜日）
            now: 現在日時（今日判定に使用）
        """
        conn = _get_shift_connection()

        # 日付リスト（7日間）
        dates = [base_date + timedelta(days=i) for i in range(7)]
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        today_str = now.strftime("%Y-%m-%d")

        # スタッフ一覧を取得
        staff_rows = conn.execute("""
            SELECT id, name, role, skills, hourly_rate
            FROM staff
            ORDER BY role DESC, name
        """).fetchall()

        staff_list = [
            {
                "id": row[0],
                "name": row[1],
                "role": row[2],
                "skills": row[3] if isinstance(row[3], list) else [],
                "hourly_rate": row[4],
            }
            for row in staff_rows
        ]

        # シフトデータを取得
        shifts = conn.execute(
            """
            SELECT staff_id, date, start_time, end_time, status
            FROM shifts
            WHERE date >= ? AND date <= ?
            ORDER BY date, start_time
            """,
            [date_strs[0], date_strs[-1]],
        ).fetchall()

        # シフトをスタッフ×日付でマッピング
        shift_map = {}
        for shift in shifts:
            staff_id, date, start, end, status = shift
            date_str = str(date)
            key = (staff_id, date_str)
            if key not in shift_map:
                shift_map[key] = []
            shift_map[key].append(
                {"start": start, "end": end, "status": status}
            )

        # 日付情報を構築
        date_info = []
        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            date_info.append({
                "date": date_str,
                "weekday": WEEKDAY_JA[d.weekday()],
                "day": d.day,
                "month": d.month,
                "is_weekend": d.weekday() >= 5,
                "is_today": date_str == today_str,
            })

        # スタッフごとのシフトを構築
        schedule = []
        total_shifts = 0
        total_hours = 0

        for staff in staff_list:
            staff_schedule = {
                "staff": staff,
                "shifts_by_date": {},
            }
            for date_str in date_strs:
                key = (staff["id"], date_str)
                shift_list = shift_map.get(key, [])
                staff_schedule["shifts_by_date"][date_str] = shift_list

                for s in shift_list:
                    if s["status"] != "cancelled":
                        total_shifts += 1
                        try:
                            start_h = int(s["start"].split(":")[0])
                            end_h = int(s["end"].split(":")[0])
                            if end_h < start_h:
                                end_h += 24
                            total_hours += end_h - start_h
                        except Exception:
                            pass

            schedule.append(staff_schedule)

        return {
            "view_type": "weekly",
            "start_date": base_date.strftime("%Y-%m-%d"),
            "end_date": dates[-1].strftime("%Y-%m-%d"),
            "generated_at": now.isoformat(),
            "dates": date_info,
            "schedule": schedule,
            "summary": {
                "total_shifts": total_shifts,
                "total_hours": total_hours,
                "staff_count": len(staff_list),
                "daily_avg_hours": round(total_hours / 7, 1) if total_hours > 0 else 0,
            },
        }

    def _get_daily_data(self, base_date: datetime, now: datetime) -> dict:
        """日次シフトデータを取得する。

        指定日のシフトと時間帯別カバレッジ（6時〜24時）を返す。

        Args:
            base_date: 対象日
            now: 現在日時
        """
        conn = _get_shift_connection()

        date_str = base_date.strftime("%Y-%m-%d")
        weekday = WEEKDAY_JA[base_date.weekday()]

        # シフトデータを取得
        shifts = conn.execute(
            """
            SELECT s.staff_id, s.start_time, s.end_time, s.status,
                   st.name, st.role, st.skills
            FROM shifts s
            JOIN staff st ON s.staff_id = st.id
            WHERE s.date = ? AND s.status != 'cancelled'
            ORDER BY s.start_time, st.name
            """,
            [date_str],
        ).fetchall()

        # 時間帯カバレッジ（6時〜24時）
        hours = list(range(6, 24))
        hourly_coverage = {h: [] for h in hours}

        staff_shifts = []
        for shift in shifts:
            staff_id, start, end, status, name, role, skills = shift
            start_h = int(start.split(":")[0])
            end_h = int(end.split(":")[0])
            if end_h < start_h:
                end_h += 24

            shift_data = {
                "staff_id": staff_id,
                "name": name,
                "role": role,
                "skills": skills if isinstance(skills, list) else [],
                "start": start,
                "end": end,
                "status": status,
            }
            staff_shifts.append(shift_data)

            # 時間帯カバレッジに追加
            for h in hours:
                if start_h <= h < end_h:
                    hourly_coverage[h].append(name)

        return {
            "view_type": "daily",
            "date": date_str,
            "weekday": weekday,
            "generated_at": now.isoformat(),
            "shifts": staff_shifts,
            "hourly_coverage": hourly_coverage,
            "summary": {
                "total_staff": len(staff_shifts),
            },
        }

    def _get_staff_view_data(self, base_date: datetime, now: datetime) -> dict:
        """スタッフ別2週間シフトデータを取得する。

        各スタッフの2週間分のシフト、合計労働時間、推定給与を返す。

        Args:
            base_date: 開始日
            now: 現在日時（今日判定に使用）
        """
        conn = _get_shift_connection()

        # 2週間分
        dates = [base_date + timedelta(days=i) for i in range(14)]
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        today_str = now.strftime("%Y-%m-%d")

        # スタッフ一覧を取得
        staff_rows = conn.execute("""
            SELECT id, name, role, hourly_rate, skills
            FROM staff
            ORDER BY role DESC, name
        """).fetchall()

        staff_list = [
            {
                "id": row[0],
                "name": row[1],
                "role": row[2],
                "hourly_rate": row[3],
                "skills": row[4] if isinstance(row[4], list) else [],
            }
            for row in staff_rows
        ]

        # シフトデータを取得
        shifts = conn.execute(
            """
            SELECT staff_id, date, start_time, end_time, status
            FROM shifts
            WHERE date >= ? AND date <= ?
            ORDER BY date, start_time
            """,
            [date_strs[0], date_strs[-1]],
        ).fetchall()

        # シフトをスタッフ×日付でマッピング
        shift_map = {}
        for shift in shifts:
            staff_id, date, start, end, status = shift
            date_str = str(date)
            key = (staff_id, date_str)
            if key not in shift_map:
                shift_map[key] = []
            shift_map[key].append({"start": start, "end": end, "status": status})

        # 日付情報を構築
        date_info = []
        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            date_info.append({
                "date": date_str,
                "weekday": WEEKDAY_JA[d.weekday()],
                "day": d.day,
                "is_weekend": d.weekday() >= 5,
                "is_today": date_str == today_str,
            })

        # スタッフごとの集計
        staff_summary = []
        for staff in staff_list:
            total_hours = 0
            shifts_by_date = {}

            for date_str in date_strs:
                key = (staff["id"], date_str)
                shift_list = shift_map.get(key, [])
                shifts_by_date[date_str] = shift_list

                for s in shift_list:
                    if s["status"] != "cancelled":
                        try:
                            start_h = int(s["start"].split(":")[0])
                            end_h = int(s["end"].split(":")[0])
                            if end_h < start_h:
                                end_h += 24
                            total_hours += end_h - start_h
                        except Exception:
                            pass

            staff_summary.append({
                "staff": staff,
                "total_hours": total_hours,
                "estimated_pay": total_hours * (staff["hourly_rate"] or 0),
                "shifts_by_date": shifts_by_date,
            })

        return {
            "view_type": "staff",
            "start_date": base_date.strftime("%Y-%m-%d"),
            "end_date": dates[-1].strftime("%Y-%m-%d"),
            "generated_at": now.isoformat(),
            "dates": date_info,
            "staff_summary": staff_summary,
        }
