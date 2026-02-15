# 在庫管理ツール

import json
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

JST = ZoneInfo("Asia/Tokyo")

_SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "inventory_manager_seed.json"
_SEED_CACHE: dict[str, Any] | None = None
_conn = None


def _load_seed_data() -> dict[str, Any]:
    global _SEED_CACHE
    if _SEED_CACHE is None:
        _SEED_CACHE = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
    return _SEED_CACHE


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect(":memory:")
        _init_schema(_conn)
    return _conn


def _get_urgency(remaining_hours: float) -> str:
    """残り時間から緊急度を判定"""
    seed = _load_seed_data()
    rules = seed["markdown_rules"]
    if remaining_hours <= rules["high"]["threshold_hours"]:
        return "high"
    elif remaining_hours <= rules["medium"]["threshold_hours"]:
        return "medium"
    else:
        return "low"


def _generate_movement_id() -> str:
    """入出庫履歴用のIDを生成"""
    return f"MOV{uuid.uuid4().hex[:8].upper()}"


class InventoryManagerTool(Tool):
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
        """在庫一覧を取得"""
        category = params.get("category", "").strip() if params.get("category") else ""
        now = datetime.now(JST)
        conn = _get_connection()

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

            # 消費期限をdatetimeに変換
            if isinstance(expires_at, str):
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                exp_dt = expires_at
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=JST)

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
        """消費期限チェック（既存のexpirationAlertロジック）"""
        category = params.get("category", "").strip() if params.get("category") else ""
        urgency_filter = params.get("urgency", "").strip().lower() if params.get("urgency") else ""
        hours_threshold = params.get("hours_threshold")

        now = datetime.now(JST)
        seed = _load_seed_data()
        rules = seed["markdown_rules"]
        conn = _get_connection()

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

            # 消費期限をdatetimeに変換
            if isinstance(expires_at, str):
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                exp_dt = expires_at
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=JST)

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
        """入荷処理"""
        item_id = params.get("item_id", "").strip() if params.get("item_id") else ""
        item_name = params.get("item_name", "").strip() if params.get("item_name") else ""
        category = params.get("category", "").strip() if params.get("category") else ""
        quantity = params.get("quantity")
        expires_in_hours = params.get("expires_in_hours")

        if not quantity or quantity <= 0:
            return {"error": "quantity は1以上の数値を指定してください"}

        now = datetime.now(JST)
        conn = _get_connection()
        seed = _load_seed_data()

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
        """出庫/販売処理"""
        item_id = params.get("item_id", "").strip() if params.get("item_id") else ""
        quantity = params.get("quantity")
        reason = params.get("reason", "販売").strip() if params.get("reason") else "販売"

        if not item_id:
            return {"error": "item_id を指定してください"}
        if not quantity or quantity <= 0:
            return {"error": "quantity は1以上の数値を指定してください"}

        now = datetime.now(JST)
        conn = _get_connection()

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
        """在庫不足アラート"""
        category = params.get("category", "").strip() if params.get("category") else ""
        conn = _get_connection()
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
        """発注推奨"""
        conn = _get_connection()
        now = datetime.now(JST)
        seed = _load_seed_data()

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
            if isinstance(expires_at, str):
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                exp_dt = expires_at
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=JST)

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
        """入出庫履歴"""
        days = params.get("days", 7) or 7
        category = params.get("category", "").strip() if params.get("category") else ""
        conn = _get_connection()
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


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """スキーマとサンプルデータを初期化"""

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
    seed = _load_seed_data()

    # 在庫データ
    for item in seed["sample_inventory"]:
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
    for movement in seed.get("sample_movements", []):
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
