"""在庫管理ツール（インメモリDuckDB）。

在庫一覧・消費期限チェック・入出庫管理・在庫不足アラート・発注推奨など、
コンビニの在庫管理業務を支援する機能を提供する。
テーブル: inventory, stock_movements。
"""

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.db_utils import DuckDBManager
from tools.datetime_utils import JST, parse_expires_at


def _get_urgency(remaining_hours: float) -> str:
    """残り時間から緊急度を判定する。

    シードデータの markdown_rules に定義されたしきい値に基づき、
    'high'・'medium'・'low' のいずれかを返す。

    Args:
        remaining_hours: 消費期限までの残り時間（時間単位）
    """
    seed = _db.load_seed_data()
    rules = seed["markdown_rules"]
    if remaining_hours <= rules["high"]["threshold_hours"]:
        return "high"
    elif remaining_hours <= rules["medium"]["threshold_hours"]:
        return "medium"
    else:
        return "low"


def _generate_movement_id() -> str:
    """入出庫履歴用のユニークIDを生成する。

    'MOV' プレフィックス + UUID先頭8文字（大文字）の形式で返す。
    """
    return f"MOV{uuid.uuid4().hex[:8].upper()}"


class InventoryManagerTool(Tool):
    """コンビニの在庫管理を行うDifyツール。

    アクションパラメータに応じて在庫一覧取得・消費期限チェック・
    入出庫処理・在庫不足アラート・発注推奨・入出庫履歴を実行する。
    """

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        action = tool_parameters.get("action", "list").strip().lower()

        try:
            if action == "list":
                result = self._action_list(tool_parameters)
            elif action == "check_expiration":
                result = self._action_check_expiration(tool_parameters)
            elif action == "add_stock":
                result = self._action_add_stock(tool_parameters)
            elif action == "remove_stock":
                result = self._action_remove_stock(tool_parameters)
            elif action == "low_stock_alert":
                result = self._action_low_stock_alert(tool_parameters)
            elif action == "order_recommendation":
                result = self._action_order_recommendation(tool_parameters)
            elif action == "movement_history":
                result = self._action_movement_history(tool_parameters)
            else:
                result = {"error": f"Unknown action: {action}"}

            yield self.create_json_message(result)

        except Exception as e:
            yield self.create_json_message({"error": str(e)})

    def _action_list(self, params: dict) -> dict:
        """在庫一覧を取得する。

        カテゴリでのフィルタリングに対応し、各商品の消費期限までの
        残り時間とカテゴリ別集計を含む一覧を返す。
        """
        category = params.get("category", "").strip() if params.get("category") else ""
        now = datetime.now(JST)
        conn = _db.get_connection()

        query = """
            SELECT item_id, item_name, category, quantity,
                   min_stock_level, reorder_point, stocked_at, expires_at
            FROM inventory
            WHERE quantity > 0
        """
        query_params = []

        if category:
            query += " AND category = ?"
            query_params.append(category)

        query += " ORDER BY category, item_name"

        result = conn.execute(query, query_params).fetchall()

        items = []
        category_summary = {}

        for row in result:
            item_id, item_name, cat, qty, min_level, reorder_pt, stocked_at, expires_at = row

            exp_dt = parse_expires_at(expires_at, now)
            remaining_hours = (exp_dt - now).total_seconds() / 3600

            items.append({
                "item_id": item_id,
                "item_name": item_name,
                "category": cat,
                "quantity": qty,
                "min_stock_level": min_level,
                "reorder_point": reorder_pt,
                "expires_at": exp_dt.isoformat(),
                "remaining_hours": round(remaining_hours, 1),
            })

            # カテゴリ別集計
            if cat not in category_summary:
                category_summary[cat] = {"count": 0, "total_quantity": 0}
            category_summary[cat]["count"] += 1
            category_summary[cat]["total_quantity"] += qty

        return {
            "current_time": now.isoformat(),
            "items": items,
            "total_items": len(items),
            "category_summary": category_summary,
        }

    def _action_check_expiration(self, params: dict) -> dict:
        """消費期限チェックを実行する。

        緊急度（high/medium/low）と時間しきい値によるフィルタリングに対応し、
        各商品の推奨アクション・割引率を含むアラート一覧を返す。
        """
        category = params.get("category", "").strip() if params.get("category") else ""
        urgency_filter = params.get("urgency", "").strip().lower() if params.get("urgency") else ""
        hours_threshold = params.get("hours_threshold")

        now = datetime.now(JST)
        seed = _db.load_seed_data()
        rules = seed["markdown_rules"]
        conn = _db.get_connection()

        query = """
            SELECT
                item_id,
                item_name,
                category,
                quantity,
                stocked_at,
                expires_at
            FROM inventory
            WHERE quantity > 0
        """
        query_params = []

        if category:
            query += " AND category = ?"
            query_params.append(category)

        query += " ORDER BY expires_at ASC"

        result = conn.execute(query, query_params).fetchall()

        alerts = []
        summary = {"high": 0, "medium": 0, "low": 0}

        for row in result:
            item_id, item_name, cat, qty, stocked_at, expires_at = row

            exp_dt = parse_expires_at(expires_at, now)
            remaining = (exp_dt - now).total_seconds() / 3600
            urgency = _get_urgency(remaining)

            # 時間しきい値でフィルタ
            if hours_threshold is not None and remaining > hours_threshold:
                continue

            # 緊急度フィルタ
            if urgency_filter and urgency != urgency_filter:
                continue

            summary[urgency] += 1

            rule = rules[urgency]
            alerts.append({
                "item_id": item_id,
                "item_name": item_name,
                "category": cat,
                "expires_at": exp_dt.isoformat(),
                "remaining_hours": round(remaining, 1),
                "quantity": qty,
                "action": rule["action"],
                "discount_percent": rule["discount"],
                "urgency": urgency,
            })

        return {
            "current_time": now.isoformat(),
            "alerts": alerts,
            "summary": {
                "high_urgency": summary["high"],
                "medium_urgency": summary["medium"],
                "low_urgency": summary["low"],
                "total": len(alerts),
            },
        }

    def _action_add_stock(self, params: dict) -> dict:
        """入荷処理を実行する。

        既存商品への追加入荷、または新規商品の登録に対応する。
        新規商品の場合はカテゴリ別のデフォルト消費期限を自動設定する。
        入出庫履歴にも自動で記録する。
        """
        item_id = params.get("item_id", "").strip() if params.get("item_id") else ""
        item_name = params.get("item_name", "").strip() if params.get("item_name") else ""
        category = params.get("category", "").strip() if params.get("category") else ""
        quantity = params.get("quantity")
        expires_in_hours = params.get("expires_in_hours")

        if not quantity or quantity <= 0:
            return {"error": "quantity は1以上の数値を指定してください"}

        now = datetime.now(JST)
        conn = _db.get_connection()
        seed = _db.load_seed_data()

        # 既存商品の確認
        existing = conn.execute(
            "SELECT item_id, item_name, category, quantity FROM inventory WHERE item_id = ?",
            [item_id]
        ).fetchone()

        if existing:
            # 既存商品に追加
            old_qty = existing[3]
            new_qty = old_qty + quantity

            conn.execute(
                "UPDATE inventory SET quantity = ? WHERE item_id = ?",
                [new_qty, item_id]
            )

            # 入出庫履歴に記録
            movement_id = _generate_movement_id()
            conn.execute(
                """
                INSERT INTO stock_movements VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [movement_id, item_id, existing[1], "in", quantity, "入荷", now.isoformat()]
            )

            return {
                "success": True,
                "action": "add_stock",
                "item_id": item_id,
                "item_name": existing[1],
                "previous_quantity": old_qty,
                "added_quantity": quantity,
                "new_quantity": new_qty,
                "movement_id": movement_id,
                "timestamp": now.isoformat(),
            }
        else:
            # 新規商品の登録
            if not item_name:
                return {"error": "新規商品には item_name が必要です"}
            if not category:
                return {"error": "新規商品には category が必要です"}

            # カテゴリのデフォルト消費期限を取得
            if expires_in_hours is None:
                expires_in_hours = seed["expiration_hours"].get(category, 8)

            # 新しいitem_idを生成（指定がない場合）
            if not item_id:
                max_id = conn.execute(
                    "SELECT MAX(CAST(SUBSTR(item_id, 4) AS INTEGER)) FROM inventory"
                ).fetchone()[0]
                new_num = (max_id or 0) + 1
                item_id = f"INV{new_num:03d}"

            stocked_at = now
            expires_at = now + timedelta(hours=expires_in_hours)

            conn.execute(
                """
                INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [item_id, item_name, category, quantity, 5, 10,
                 stocked_at.isoformat(), expires_at.isoformat()]
            )

            # 入出庫履歴に記録
            movement_id = _generate_movement_id()
            conn.execute(
                """
                INSERT INTO stock_movements VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [movement_id, item_id, item_name, "in", quantity, "新規入荷", now.isoformat()]
            )

            return {
                "success": True,
                "action": "add_stock",
                "item_id": item_id,
                "item_name": item_name,
                "category": category,
                "quantity": quantity,
                "expires_at": expires_at.isoformat(),
                "movement_id": movement_id,
                "timestamp": now.isoformat(),
            }

    def _action_remove_stock(self, params: dict) -> dict:
        """出庫・販売処理を実行する。

        指定された商品の在庫を減少させ、入出庫履歴に記録する。
        理由に「廃棄」「期限」が含まれる場合は movement_type を 'expired' に設定する。
        """
        item_id = params.get("item_id", "").strip() if params.get("item_id") else ""
        quantity = params.get("quantity")
        reason = params.get("reason", "販売").strip() if params.get("reason") else "販売"

        if not item_id:
            return {"error": "item_id を指定してください"}
        if not quantity or quantity <= 0:
            return {"error": "quantity は1以上の数値を指定してください"}

        now = datetime.now(JST)
        conn = _db.get_connection()

        # 既存商品の確認
        existing = conn.execute(
            "SELECT item_id, item_name, quantity FROM inventory WHERE item_id = ?",
            [item_id]
        ).fetchone()

        if not existing:
            return {"error": f"商品が見つかりません: {item_id}"}

        old_qty = existing[2]
        if quantity > old_qty:
            return {
                "error": f"在庫不足です。現在の在庫: {old_qty}、出庫要求: {quantity}"
            }

        new_qty = old_qty - quantity

        conn.execute(
            "UPDATE inventory SET quantity = ? WHERE item_id = ?",
            [new_qty, item_id]
        )

        # 入出庫履歴に記録
        movement_type = "expired" if "廃棄" in reason or "期限" in reason else "out"
        movement_id = _generate_movement_id()
        conn.execute(
            """
            INSERT INTO stock_movements VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [movement_id, item_id, existing[1], movement_type, quantity, reason, now.isoformat()]
        )

        return {
            "success": True,
            "action": "remove_stock",
            "item_id": item_id,
            "item_name": existing[1],
            "previous_quantity": old_qty,
            "removed_quantity": quantity,
            "new_quantity": new_qty,
            "reason": reason,
            "movement_id": movement_id,
            "timestamp": now.isoformat(),
        }

    def _action_low_stock_alert(self, params: dict) -> dict:
        """在庫不足アラートを生成する。

        発注点（reorder_point）以下の商品を検出し、
        最低在庫レベル以下は 'critical'、発注点以下は 'warning' として分類する。
        推奨発注数量も算出して返す。
        """
        category = params.get("category", "").strip() if params.get("category") else ""
        conn = _db.get_connection()
        now = datetime.now(JST)

        query = """
            SELECT item_id, item_name, category, quantity,
                   min_stock_level, reorder_point,
                   (reorder_point - quantity) as shortage
            FROM inventory
            WHERE quantity <= reorder_point
        """
        query_params = []

        if category:
            query += " AND category = ?"
            query_params.append(category)

        query += " ORDER BY shortage DESC, category, item_name"

        result = conn.execute(query, query_params).fetchall()

        alerts = []
        critical_count = 0
        warning_count = 0

        for row in result:
            item_id, item_name, cat, qty, min_level, reorder_pt, shortage = row

            # 最低在庫レベル以下は「緊急」、発注点以下は「警告」
            if qty <= min_level:
                level = "critical"
                critical_count += 1
            else:
                level = "warning"
                warning_count += 1

            recommended_order = reorder_pt - qty + 5  # 発注点 + バッファ

            alerts.append({
                "item_id": item_id,
                "item_name": item_name,
                "category": cat,
                "current_quantity": qty,
                "min_stock_level": min_level,
                "reorder_point": reorder_pt,
                "shortage": shortage,
                "recommended_order_quantity": max(recommended_order, 0),
                "alert_level": level,
            })

        return {
            "current_time": now.isoformat(),
            "alerts": alerts,
            "summary": {
                "critical_count": critical_count,
                "warning_count": warning_count,
                "total": len(alerts),
            },
        }

    def _action_order_recommendation(self, params: dict) -> dict:
        """発注推奨リストを生成する。

        発注点以下の全商品を対象に、消費期限の残り時間を考慮して
        最適な発注数量を算出する。期限切れ間近の商品は発注を見送る。
        """
        conn = _db.get_connection()
        now = datetime.now(JST)

        # 発注点以下の商品を取得
        result = conn.execute("""
            SELECT item_id, item_name, category, quantity,
                   min_stock_level, reorder_point, expires_at
            FROM inventory
            WHERE quantity <= reorder_point
            ORDER BY (reorder_point - quantity) DESC
        """).fetchall()

        recommendations = []
        total_items_to_order = 0

        for row in result:
            item_id, item_name, cat, qty, min_level, reorder_pt, expires_at = row

            # 消費期限をチェック
            exp_dt = parse_expires_at(expires_at, now)
            remaining_hours = (exp_dt - now).total_seconds() / 3600

            # 基本発注数量: 発注点 + バッファ - 現在庫
            base_order = reorder_pt + 5 - qty

            # 消費期限が近い場合は発注を控えめに
            if remaining_hours < 4:
                # 期限切れ間近は発注しない
                order_quantity = 0
                note = "期限切れ間近のため発注見送り"
            elif remaining_hours < 8:
                order_quantity = max(0, base_order // 2)
                note = "期限が近いため少量発注推奨"
            else:
                order_quantity = max(0, base_order)
                note = "通常発注"

            if order_quantity > 0:
                total_items_to_order += order_quantity

            recommendations.append({
                "item_id": item_id,
                "item_name": item_name,
                "category": cat,
                "current_quantity": qty,
                "reorder_point": reorder_pt,
                "shortage": reorder_pt - qty,
                "recommended_order_quantity": order_quantity,
                "remaining_hours_until_expiry": round(remaining_hours, 1),
                "note": note,
            })

        # カテゴリ別の発注推奨数
        category_orders = {}
        for rec in recommendations:
            cat = rec["category"]
            if cat not in category_orders:
                category_orders[cat] = 0
            category_orders[cat] += rec["recommended_order_quantity"]

        return {
            "current_time": now.isoformat(),
            "recommendations": recommendations,
            "category_orders": category_orders,
            "summary": {
                "total_items": len(recommendations),
                "total_quantity_to_order": total_items_to_order,
            },
        }

    def _action_movement_history(self, params: dict) -> dict:
        """入出庫履歴を取得する。

        指定期間（デフォルト7日間）の入出庫履歴を返す。
        カテゴリフィルタにも対応し、入荷・出庫・廃棄の集計も行う。
        """
        days = params.get("days", 7) or 7
        category = params.get("category", "").strip() if params.get("category") else ""
        conn = _db.get_connection()
        now = datetime.now(JST)

        cutoff = now - timedelta(days=days)

        query = """
            SELECT m.movement_id, m.item_id, m.item_name, m.movement_type,
                   m.quantity, m.reason, m.created_at
            FROM stock_movements m
            WHERE m.created_at >= ?
        """
        query_params = [cutoff.isoformat()]

        if category:
            # カテゴリでフィルタする場合は inventory テーブルと JOIN
            query = """
                SELECT m.movement_id, m.item_id, m.item_name, m.movement_type,
                       m.quantity, m.reason, m.created_at
                FROM stock_movements m
                JOIN inventory i ON m.item_id = i.item_id
                WHERE m.created_at >= ?
                  AND i.category = ?
            """
            query_params.append(category)

        query += " ORDER BY m.created_at DESC"

        result = conn.execute(query, query_params).fetchall()

        movements = []
        summary = {"in": 0, "out": 0, "expired": 0}

        for row in result:
            movement_id, item_id, item_name, movement_type, qty, reason, created_at = row

            # 集計
            if movement_type in summary:
                summary[movement_type] += qty

            movements.append({
                "movement_id": movement_id,
                "item_id": item_id,
                "item_name": item_name,
                "movement_type": movement_type,
                "quantity": qty,
                "reason": reason,
                "created_at": created_at if isinstance(created_at, str) else created_at.isoformat(),
            })

        return {
            "current_time": now.isoformat(),
            "period_days": days,
            "movements": movements,
            "summary": {
                "total_in": summary["in"],
                "total_out": summary["out"],
                "total_expired": summary["expired"],
                "total_movements": len(movements),
            },
        }


def _init_schema(conn: duckdb.DuckDBPyConnection, seed_data: dict[str, Any]) -> None:
    """スキーマとサンプルデータを初期化する。

    inventory テーブルと stock_movements テーブルを作成し、
    シードデータから現在時刻基準のサンプルデータを投入する。

    Args:
        conn: DuckDBインメモリ接続
        seed_data: シードデータ辞書（sample_inventory, sample_movements等を含む）
    """

    # inventory テーブル（拡張）
    conn.execute("""
        CREATE TABLE inventory (
            item_id VARCHAR PRIMARY KEY,
            item_name VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            min_stock_level INTEGER NOT NULL DEFAULT 5,
            reorder_point INTEGER NOT NULL DEFAULT 10,
            stocked_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
    """)

    # stock_movements テーブル（新規）
    conn.execute("""
        CREATE TABLE stock_movements (
            movement_id VARCHAR PRIMARY KEY,
            item_id VARCHAR NOT NULL,
            item_name VARCHAR NOT NULL,
            movement_type VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            reason VARCHAR,
            created_at TIMESTAMP NOT NULL
        )
    """)

    # サンプルデータを生成（現在時刻基準）
    now = datetime.now(JST)

    # 在庫データ
    for item in seed_data["sample_inventory"]:
        stocked_at = now - timedelta(hours=item["stocked_hours_ago"])
        expires_at = now + timedelta(hours=item["expires_in_hours"])

        conn.execute(
            """
            INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                item["item_id"],
                item["item_name"],
                item["category"],
                item["quantity"],
                item.get("min_stock_level", 5),
                item.get("reorder_point", 10),
                stocked_at.isoformat(),
                expires_at.isoformat(),
            ],
        )

    # 入出庫履歴データ
    for movement in seed_data.get("sample_movements", []):
        created_at = now - timedelta(hours=movement["hours_ago"])

        conn.execute(
            """
            INSERT INTO stock_movements VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                movement["movement_id"],
                movement["item_id"],
                movement["item_name"],
                movement["movement_type"],
                movement["quantity"],
                movement["reason"],
                created_at.isoformat(),
            ],
        )


_db = DuckDBManager("inventory_manager_seed.json", _init_schema)
