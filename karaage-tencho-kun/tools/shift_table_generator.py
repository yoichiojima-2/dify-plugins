# シフト表生成ツール

from collections.abc import Generator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# shift_managerの接続を再利用
from tools.shift_manager import _get_connection as _get_shift_connection

JST = ZoneInfo("Asia/Tokyo")

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]

# スキル別の色
SKILL_COLORS = {
    "からあげ": "#FF6B35",
    "レジ": "#4ECDC4",
    "品出し": "#45B7D1",
    "発注": "#96CEB4",
    "清掃": "#FFEAA7",
    "クレーム対応": "#DDA0DD",
}

# 役職別の背景色
ROLE_COLORS = {
    "manager": "#E8F5E9",
    "part_time": "#FFF8E1",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
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
        .container {{
            max-width: 1400px;
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
        .legend {{
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
        }}
        .shift-table-container {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        .shift-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        .shift-table th {{
            background: #f8f9fa;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
            white-space: nowrap;
        }}
        .shift-table th.weekend {{
            background: #fff3e0;
        }}
        .shift-table th.today {{
            background: #e3f2fd;
            color: #1976d2;
        }}
        .shift-table td {{
            padding: 8px;
            border-bottom: 1px solid #eee;
            vertical-align: top;
        }}
        .shift-table td.staff-name {{
            font-weight: 500;
            white-space: nowrap;
            min-width: 100px;
        }}
        .shift-table td.staff-name.manager {{
            background: #E8F5E9;
        }}
        .shift-cell {{
            min-width: 80px;
            text-align: center;
        }}
        .shift-block {{
            background: #e3f2fd;
            border-radius: 6px;
            padding: 6px 8px;
            margin: 2px 0;
            font-size: 12px;
            position: relative;
        }}
        .shift-block.manager {{
            background: #c8e6c9;
            border-left: 3px solid #4caf50;
        }}
        .shift-block.pending {{
            background: #fff3e0;
            border-left: 3px solid #ff9800;
        }}
        .shift-block.cancelled {{
            background: #ffebee;
            text-decoration: line-through;
            opacity: 0.6;
        }}
        .shift-time {{
            font-weight: 500;
        }}
        .skill-badges {{
            display: flex;
            gap: 3px;
            margin-top: 4px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        .skill-badge {{
            font-size: 10px;
            padding: 2px 5px;
            border-radius: 3px;
            color: white;
        }}
        .no-shift {{
            color: #ccc;
            font-size: 12px;
        }}
        .summary {{
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-top: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .summary h3 {{
            font-size: 16px;
            margin-bottom: 12px;
            color: #333;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }}
        .summary-item {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .summary-label {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
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
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p class="subtitle">生成日時: {generated_at} | 期間: {period}</p>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #c8e6c9; border-left: 3px solid #4caf50;"></div>
                <span>店長</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #e3f2fd;"></div>
                <span>確定シフト</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #fff3e0; border-left: 3px solid #ff9800;"></div>
                <span>仮シフト</span>
            </div>
            {skill_legend}
        </div>

        <div class="shift-table-container">
            <table class="shift-table">
                {table_content}
            </table>
        </div>

        <div class="summary">
            <h3>週間サマリー</h3>
            <div class="summary-grid">
                {summary_items}
            </div>
        </div>

        <div class="footer">
            からあげ店長クン - シフト管理表
        </div>
    </div>
</body>
</html>"""


class ShiftTableGeneratorTool(Tool):
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
                html = self._generate_weekly_table(base_date, now)
            elif view_type == "daily":
                html = self._generate_daily_table(base_date, now)
            elif view_type == "staff":
                html = self._generate_staff_view(base_date, now)
            else:
                yield self.create_json_message(
                    {
                        "error": f"不明なビュータイプ: {view_type}",
                        "available_types": ["weekly", "daily", "staff"],
                    }
                )
                return

            yield self.create_json_message(
                {
                    "view_type": view_type,
                    "start_date": base_date.strftime("%Y-%m-%d"),
                    "generated_at": now.isoformat(),
                    "html": html,
                }
            )

        except ValueError as e:
            yield self.create_json_message(
                {
                    "error": f"日付形式エラー: {e}",
                    "hint": "YYYY-MM-DD 形式で指定してください",
                }
            )
        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _generate_weekly_table(self, base_date: datetime, now: datetime) -> str:
        """週間シフト表を生成（スタッフ×日付）"""
        conn = _get_shift_connection()

        # 日付リスト（7日間）
        dates = [base_date + timedelta(days=i) for i in range(7)]
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]

        # スタッフ一覧を取得
        staff_list = conn.execute("""
            SELECT id, name, role, skills
            FROM staff
            ORDER BY role DESC, name
        """).fetchall()

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

        # ヘッダー行
        today_str = now.strftime("%Y-%m-%d")
        header_cells = ["<th>スタッフ</th>"]
        for i, d in enumerate(dates):
            date_str = d.strftime("%Y-%m-%d")
            weekday = WEEKDAY_JA[d.weekday()]
            day_num = d.day

            classes = []
            if d.weekday() >= 5:
                classes.append("weekend")
            if date_str == today_str:
                classes.append("today")

            class_str = f' class="{" ".join(classes)}"' if classes else ""
            header_cells.append(f"<th{class_str}>{d.month}/{day_num}({weekday})</th>")

        header_row = "<tr>" + "".join(header_cells) + "</tr>"

        # データ行
        data_rows = []
        total_shifts = 0
        total_hours = 0

        for staff in staff_list:
            staff_id, name, role, skills = staff
            skills_list = skills if isinstance(skills, list) else []

            row_cells = []

            # スタッフ名セル
            name_class = "staff-name"
            if role == "manager":
                name_class += " manager"
            row_cells.append(f'<td class="{name_class}">{name}</td>')

            # 各日のシフト
            for date_str in date_strs:
                key = (staff_id, date_str)
                shift_list = shift_map.get(key, [])

                if shift_list:
                    blocks = []
                    for s in shift_list:
                        block_class = "shift-block"
                        if role == "manager":
                            block_class += " manager"
                        if s["status"] == "pending":
                            block_class += " pending"
                        elif s["status"] == "cancelled":
                            block_class += " cancelled"

                        # 勤務時間を計算
                        if s["status"] != "cancelled":
                            try:
                                start_h = int(s["start"].split(":")[0])
                                end_h = int(s["end"].split(":")[0])
                                if end_h < start_h:
                                    end_h += 24
                                total_hours += end_h - start_h
                                total_shifts += 1
                            except Exception:
                                pass

                        # スキルバッジ
                        badges = []
                        for skill in skills_list[:3]:  # 最大3つ
                            color = SKILL_COLORS.get(skill, "#888")
                            badges.append(
                                f'<span class="skill-badge" style="background:{color}">{skill}</span>'
                            )

                        badge_html = (
                            f'<div class="skill-badges">{"".join(badges)}</div>'
                            if badges
                            else ""
                        )

                        blocks.append(
                            f'<div class="{block_class}">'
                            f'<div class="shift-time">{s["start"]}-{s["end"]}</div>'
                            f"{badge_html}</div>"
                        )

                    row_cells.append(
                        f'<td class="shift-cell">{"".join(blocks)}</td>'
                    )
                else:
                    row_cells.append('<td class="shift-cell"><span class="no-shift">-</span></td>')

            data_rows.append("<tr>" + "".join(row_cells) + "</tr>")

        table_content = f"<thead>{header_row}</thead><tbody>{''.join(data_rows)}</tbody>"

        # スキル凡例
        skill_legend = "".join(
            f'<div class="legend-item">'
            f'<div class="legend-color" style="background:{color}"></div>'
            f"<span>{skill}</span></div>"
            for skill, color in SKILL_COLORS.items()
        )

        # サマリー
        summary_items = f"""
            <div class="summary-item">
                <div class="summary-value">{total_shifts}</div>
                <div class="summary-label">総シフト数</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{total_hours}</div>
                <div class="summary-label">総労働時間</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{len(staff_list)}</div>
                <div class="summary-label">スタッフ数</div>
            </div>
            <div class="summary-item">
                <div class="summary-value">{total_hours / 7:.1f}</div>
                <div class="summary-label">日平均労働時間</div>
            </div>
        """

        return HTML_TEMPLATE.format(
            title="週間シフト表",
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period=f"{dates[0].month}/{dates[0].day}({WEEKDAY_JA[dates[0].weekday()]}) 〜 {dates[-1].month}/{dates[-1].day}({WEEKDAY_JA[dates[-1].weekday()]})",
            skill_legend=skill_legend,
            table_content=table_content,
            summary_items=summary_items,
        )

    def _generate_daily_table(self, base_date: datetime, now: datetime) -> str:
        """日次シフト表を生成（時間帯×スタッフ）"""
        conn = _get_shift_connection()

        date_str = base_date.strftime("%Y-%m-%d")
        weekday = WEEKDAY_JA[base_date.weekday()]

        # シフトデータを取得
        shifts = conn.execute(
            """
            SELECT s.staff_id, s.start_time, s.end_time, s.status, st.name, st.role, st.skills
            FROM shifts s
            JOIN staff st ON s.staff_id = st.id
            WHERE s.date = ? AND s.status != 'cancelled'
            ORDER BY s.start_time, st.name
            """,
            [date_str],
        ).fetchall()

        # 時間帯（6時〜24時）
        hours = list(range(6, 24))

        # ヘッダー行
        header_cells = ["<th>スタッフ</th>"]
        for h in hours:
            header_cells.append(f"<th>{h}:00</th>")
        header_row = "<tr>" + "".join(header_cells) + "</tr>"

        # シフトをスタッフごとにグループ化
        staff_shifts = {}
        for shift in shifts:
            staff_id, start, end, status, name, role, skills = shift
            if staff_id not in staff_shifts:
                staff_shifts[staff_id] = {
                    "name": name,
                    "role": role,
                    "skills": skills if isinstance(skills, list) else [],
                    "shifts": [],
                }
            staff_shifts[staff_id]["shifts"].append(
                {"start": start, "end": end, "status": status}
            )

        # データ行
        data_rows = []
        for staff_id, data in staff_shifts.items():
            row_cells = []

            # スタッフ名
            name_class = "staff-name"
            if data["role"] == "manager":
                name_class += " manager"
            row_cells.append(f'<td class="{name_class}">{data["name"]}</td>')

            # 各時間帯
            for h in hours:
                is_working = False
                for s in data["shifts"]:
                    start_h = int(s["start"].split(":")[0])
                    end_h = int(s["end"].split(":")[0])
                    if end_h < start_h:
                        end_h += 24
                    if start_h <= h < end_h:
                        is_working = True
                        break

                if is_working:
                    color = "#c8e6c9" if data["role"] == "manager" else "#e3f2fd"
                    row_cells.append(
                        f'<td style="background:{color}; text-align:center;">●</td>'
                    )
                else:
                    row_cells.append('<td style="text-align:center;">-</td>')

            data_rows.append("<tr>" + "".join(row_cells) + "</tr>")

        table_content = f"<thead>{header_row}</thead><tbody>{''.join(data_rows)}</tbody>"

        # スキル凡例（日次では簡略化）
        skill_legend = ""

        # サマリー
        total_staff = len(staff_shifts)
        summary_items = f"""
            <div class="summary-item">
                <div class="summary-value">{total_staff}</div>
                <div class="summary-label">出勤スタッフ数</div>
            </div>
        """

        return HTML_TEMPLATE.format(
            title=f"日次シフト表 - {base_date.month}/{base_date.day}({weekday})",
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period=f"{base_date.year}年{base_date.month}月{base_date.day}日（{weekday}）",
            skill_legend=skill_legend,
            table_content=table_content,
            summary_items=summary_items,
        )

    def _generate_staff_view(self, base_date: datetime, now: datetime) -> str:
        """スタッフ別ビューを生成（2週間分）"""
        conn = _get_shift_connection()

        # 2週間分
        dates = [base_date + timedelta(days=i) for i in range(14)]
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]

        # スタッフ一覧を取得
        staff_list = conn.execute("""
            SELECT id, name, role, hourly_rate, skills
            FROM staff
            ORDER BY role DESC, name
        """).fetchall()

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

        # ヘッダー行（2週間分）
        today_str = now.strftime("%Y-%m-%d")
        header_cells = ["<th>スタッフ</th>", "<th>時給</th>"]
        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            weekday = WEEKDAY_JA[d.weekday()]
            day_num = d.day

            classes = []
            if d.weekday() >= 5:
                classes.append("weekend")
            if date_str == today_str:
                classes.append("today")

            class_str = f' class="{" ".join(classes)}"' if classes else ""
            header_cells.append(f"<th{class_str}>{day_num}<br>{weekday}</th>")

        header_row = "<tr>" + "".join(header_cells) + "</tr>"

        # データ行
        data_rows = []
        for staff in staff_list:
            staff_id, name, role, hourly_rate, skills = staff

            row_cells = []

            # スタッフ名
            name_class = "staff-name"
            if role == "manager":
                name_class += " manager"
            row_cells.append(f'<td class="{name_class}">{name}</td>')

            # 時給
            row_cells.append(f"<td style='text-align:center'>¥{hourly_rate:,}</td>")

            # 各日のシフト
            staff_hours = 0
            for date_str in date_strs:
                key = (staff_id, date_str)
                shift_list = shift_map.get(key, [])

                if shift_list:
                    times = []
                    for s in shift_list:
                        if s["status"] != "cancelled":
                            times.append(f"{s['start'][:2]}-{s['end'][:2]}")
                            try:
                                start_h = int(s["start"].split(":")[0])
                                end_h = int(s["end"].split(":")[0])
                                if end_h < start_h:
                                    end_h += 24
                                staff_hours += end_h - start_h
                            except Exception:
                                pass

                    color = "#c8e6c9" if role == "manager" else "#e3f2fd"
                    row_cells.append(
                        f'<td style="background:{color}; text-align:center; font-size:10px">'
                        f'{"<br>".join(times)}</td>'
                    )
                else:
                    row_cells.append('<td style="text-align:center; color:#ccc">-</td>')

            data_rows.append("<tr>" + "".join(row_cells) + "</tr>")

        table_content = f"<thead>{header_row}</thead><tbody>{''.join(data_rows)}</tbody>"

        # サマリー
        summary_items = f"""
            <div class="summary-item">
                <div class="summary-value">{len(staff_list)}</div>
                <div class="summary-label">登録スタッフ数</div>
            </div>
        """

        return HTML_TEMPLATE.format(
            title="スタッフ別シフト一覧（2週間）",
            generated_at=now.strftime("%Y-%m-%d %H:%M"),
            period=f"{dates[0].month}/{dates[0].day} 〜 {dates[-1].month}/{dates[-1].day}",
            skill_legend="",
            table_content=table_content,
            summary_items=summary_items,
        )
