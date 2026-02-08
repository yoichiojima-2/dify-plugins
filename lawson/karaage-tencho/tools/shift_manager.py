# シフト管理ツール - SQL版 (インメモリDB)

from collections.abc import Generator

import duckdb
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# インメモリDBを使用（Difyクラウド環境はファイルシステムが読み取り専用のため）
_conn = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect(":memory:")
        _init_schema(_conn)
    return _conn


class ShiftManagerTool(Tool):
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
    # スキーマ作成
    conn.execute("""
        CREATE TABLE staff (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            name_reading VARCHAR,
            role VARCHAR,
            role_ja VARCHAR,
            hourly_rate INTEGER,
            skills VARCHAR[],
            availability JSON,
            preferred_hours INTEGER,
            phone VARCHAR,
            line_id VARCHAR,
            color VARCHAR,
            notes VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE shifts (
            shift_id VARCHAR PRIMARY KEY,
            staff_id VARCHAR NOT NULL,
            staff_name VARCHAR NOT NULL,
            date DATE NOT NULL,
            start_time VARCHAR NOT NULL,
            end_time VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'confirmed',
            created_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancel_reason VARCHAR,
            swapped_from VARCHAR,
            swapped_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE swap_requests (
            swap_id VARCHAR PRIMARY KEY,
            shift_id VARCHAR NOT NULL,
            original_staff_id VARCHAR NOT NULL,
            original_staff_name VARCHAR NOT NULL,
            date DATE NOT NULL,
            start_time VARCHAR NOT NULL,
            end_time VARCHAR NOT NULL,
            reason VARCHAR,
            status VARCHAR DEFAULT 'pending',
            requested_at TIMESTAMP,
            approved_staff_id VARCHAR,
            approved_staff_name VARCHAR,
            approved_at TIMESTAMP
        )
    """)

    # デフォルトスタッフ
    conn.execute("""
        INSERT INTO staff VALUES
        ('tanaka', '田中太郎', 'たなかたろう', 'manager', '店長', 1500,
         ['レジ', 'からあげ', '発注', 'クレーム対応'],
         '{"mon": ["06:00-15:00"], "tue": ["06:00-15:00"], "wed": ["06:00-15:00"], "thu": ["06:00-15:00"], "fri": ["06:00-15:00"]}',
         40, '090-1234-5678', 'tanaka_taro', '#4CAF50', '店長。朝型シフト。'),

        ('sato', '佐藤花子', 'さとうはなこ', 'part_time', 'パート', 1100,
         ['レジ', 'からあげ', '清掃'],
         '{"mon": ["09:00-17:00"], "wed": ["09:00-17:00"], "fri": ["09:00-17:00"]}',
         20, '090-2345-6789', 'sato_hanako', '#E91E63', '主婦パート。平日昼間希望。'),

        ('suzuki', '鈴木健一', 'すずきけんいち', 'part_time', 'パート', 1100,
         ['レジ', 'からあげ', '品出し'],
         '{"tue": ["17:00-22:00"], "thu": ["17:00-22:00"], "sat": ["10:00-18:00"], "sun": ["10:00-18:00"]}',
         25, '090-3456-7890', 'suzuki_ken', '#2196F3', '大学生。夕方と週末可。'),

        ('yamada', '山田美咲', 'やまだみさき', 'part_time', 'パート', 1100,
         ['レジ', '清掃'],
         '{"mon": ["18:00-22:00"], "tue": ["18:00-22:00"], "wed": ["18:00-22:00"], "thu": ["18:00-22:00"], "fri": ["18:00-22:00"]}',
         20, '090-4567-8901', 'yamada_m', '#FF9800', '高校生。平日夜のみ。'),

        ('takahashi', '高橋翔', 'たかはししょう', 'part_time', 'パート', 1300,
         ['レジ', 'からあげ', '品出し', '発注'],
         '{"sat": ["06:00-14:00"], "sun": ["06:00-14:00"], "mon": ["22:00-06:00"], "wed": ["22:00-06:00"]}',
         30, '090-5678-9012', 'taka_sho', '#9C27B0', 'フリーター。深夜・週末可。'),

        ('ito', '伊藤優', 'いとうゆう', 'part_time', 'パート', 1100,
         ['レジ', 'からあげ'],
         '{"tue": ["10:00-16:00"], "thu": ["10:00-16:00"], "sat": ["14:00-20:00"]}',
         15, '090-6789-0123', 'ito_yu', '#00BCD4', '大学生。週3日希望。'),

        ('watanabe', '渡辺リサ', 'わたなべりさ', 'part_time', 'パート', 1100,
         ['レジ', '清掃', '品出し'],
         '{"mon": ["14:00-20:00"], "wed": ["14:00-20:00"], "fri": ["14:00-20:00"], "sun": ["14:00-20:00"]}',
         20, '090-7890-1234', 'watanabe_r', '#795548', '主婦パート。午後希望。')
    """)

    # サンプルシフト（過去2週間 + 今日から2週間分 = 約4週間分）
    conn.execute("""
        INSERT INTO shifts VALUES
        -- 2週間前
        ('SH001', 'tanaka', '田中太郎', CURRENT_DATE - 14, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 14 DAY, NULL, NULL, NULL, NULL),
        ('SH002', 'sato', '佐藤花子', CURRENT_DATE - 14, '09:00', '17:00', 'confirmed', NOW() - INTERVAL 14 DAY, NULL, NULL, NULL, NULL),
        ('SH003', 'yamada', '山田美咲', CURRENT_DATE - 14, '18:00', '22:00', 'confirmed', NOW() - INTERVAL 14 DAY, NULL, NULL, NULL, NULL),
        ('SH004', 'takahashi', '高橋翔', CURRENT_DATE - 14, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 14 DAY, NULL, NULL, NULL, NULL),
        ('SH005', 'tanaka', '田中太郎', CURRENT_DATE - 13, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 13 DAY, NULL, NULL, NULL, NULL),
        ('SH006', 'suzuki', '鈴木健一', CURRENT_DATE - 13, '17:00', '22:00', 'confirmed', NOW() - INTERVAL 13 DAY, NULL, NULL, NULL, NULL),
        ('SH007', 'ito', '伊藤優', CURRENT_DATE - 13, '10:00', '16:00', 'confirmed', NOW() - INTERVAL 13 DAY, NULL, NULL, NULL, NULL),
        ('SH008', 'takahashi', '高橋翔', CURRENT_DATE - 13, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 13 DAY, NULL, NULL, NULL, NULL),
        ('SH009', 'tanaka', '田中太郎', CURRENT_DATE - 12, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 12 DAY, NULL, NULL, NULL, NULL),
        ('SH010', 'sato', '佐藤花子', CURRENT_DATE - 12, '09:00', '17:00', 'confirmed', NOW() - INTERVAL 12 DAY, NULL, NULL, NULL, NULL),
        ('SH011', 'watanabe', '渡辺リサ', CURRENT_DATE - 12, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 12 DAY, NULL, NULL, NULL, NULL),
        ('SH012', 'yamada', '山田美咲', CURRENT_DATE - 12, '18:00', '22:00', 'confirmed', NOW() - INTERVAL 12 DAY, NULL, NULL, NULL, NULL),
        ('SH013', 'tanaka', '田中太郎', CURRENT_DATE - 11, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 11 DAY, NULL, NULL, NULL, NULL),
        ('SH014', 'suzuki', '鈴木健一', CURRENT_DATE - 11, '17:00', '22:00', 'confirmed', NOW() - INTERVAL 11 DAY, NULL, NULL, NULL, NULL),
        ('SH015', 'ito', '伊藤優', CURRENT_DATE - 11, '10:00', '16:00', 'confirmed', NOW() - INTERVAL 11 DAY, NULL, NULL, NULL, NULL),
        ('SH016', 'takahashi', '高橋翔', CURRENT_DATE - 11, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 11 DAY, NULL, NULL, NULL, NULL),
        ('SH017', 'tanaka', '田中太郎', CURRENT_DATE - 10, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 10 DAY, NULL, NULL, NULL, NULL),
        ('SH018', 'sato', '佐藤花子', CURRENT_DATE - 10, '09:00', '17:00', 'confirmed', NOW() - INTERVAL 10 DAY, NULL, NULL, NULL, NULL),
        ('SH019', 'yamada', '山田美咲', CURRENT_DATE - 10, '18:00', '22:00', 'confirmed', NOW() - INTERVAL 10 DAY, NULL, NULL, NULL, NULL),
        ('SH020', 'takahashi', '高橋翔', CURRENT_DATE - 10, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 10 DAY, NULL, NULL, NULL, NULL),
        -- 週末（2週間前の土日）
        ('SH021', 'suzuki', '鈴木健一', CURRENT_DATE - 9, '10:00', '18:00', 'confirmed', NOW() - INTERVAL 9 DAY, NULL, NULL, NULL, NULL),
        ('SH022', 'watanabe', '渡辺リサ', CURRENT_DATE - 9, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 9 DAY, NULL, NULL, NULL, NULL),
        ('SH023', 'takahashi', '高橋翔', CURRENT_DATE - 9, '06:00', '14:00', 'confirmed', NOW() - INTERVAL 9 DAY, NULL, NULL, NULL, NULL),
        ('SH024', 'ito', '伊藤優', CURRENT_DATE - 9, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 9 DAY, NULL, NULL, NULL, NULL),
        ('SH025', 'suzuki', '鈴木健一', CURRENT_DATE - 8, '10:00', '18:00', 'confirmed', NOW() - INTERVAL 8 DAY, NULL, NULL, NULL, NULL),
        ('SH026', 'watanabe', '渡辺リサ', CURRENT_DATE - 8, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 8 DAY, NULL, NULL, NULL, NULL),
        ('SH027', 'takahashi', '高橋翔', CURRENT_DATE - 8, '06:00', '14:00', 'confirmed', NOW() - INTERVAL 8 DAY, NULL, NULL, NULL, NULL),
        -- 1週間前（平日）
        ('SH028', 'tanaka', '田中太郎', CURRENT_DATE - 7, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 7 DAY, NULL, NULL, NULL, NULL),
        ('SH029', 'sato', '佐藤花子', CURRENT_DATE - 7, '09:00', '17:00', 'confirmed', NOW() - INTERVAL 7 DAY, NULL, NULL, NULL, NULL),
        ('SH030', 'yamada', '山田美咲', CURRENT_DATE - 7, '18:00', '22:00', 'confirmed', NOW() - INTERVAL 7 DAY, NULL, NULL, NULL, NULL),
        ('SH031', 'takahashi', '高橋翔', CURRENT_DATE - 7, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 7 DAY, NULL, NULL, NULL, NULL),
        ('SH032', 'tanaka', '田中太郎', CURRENT_DATE - 6, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 6 DAY, NULL, NULL, NULL, NULL),
        ('SH033', 'suzuki', '鈴木健一', CURRENT_DATE - 6, '17:00', '22:00', 'confirmed', NOW() - INTERVAL 6 DAY, NULL, NULL, NULL, NULL),
        ('SH034', 'ito', '伊藤優', CURRENT_DATE - 6, '10:00', '16:00', 'confirmed', NOW() - INTERVAL 6 DAY, NULL, NULL, NULL, NULL),
        ('SH035', 'takahashi', '高橋翔', CURRENT_DATE - 6, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 6 DAY, NULL, NULL, NULL, NULL),
        ('SH036', 'tanaka', '田中太郎', CURRENT_DATE - 5, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 5 DAY, NULL, NULL, NULL, NULL),
        ('SH037', 'sato', '佐藤花子', CURRENT_DATE - 5, '09:00', '17:00', 'confirmed', NOW() - INTERVAL 5 DAY, NULL, NULL, NULL, NULL),
        ('SH038', 'watanabe', '渡辺リサ', CURRENT_DATE - 5, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 5 DAY, NULL, NULL, NULL, NULL),
        ('SH039', 'yamada', '山田美咲', CURRENT_DATE - 5, '18:00', '22:00', 'confirmed', NOW() - INTERVAL 5 DAY, NULL, NULL, NULL, NULL),
        ('SH040', 'takahashi', '高橋翔', CURRENT_DATE - 5, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 5 DAY, NULL, NULL, NULL, NULL),
        ('SH041', 'tanaka', '田中太郎', CURRENT_DATE - 4, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 4 DAY, NULL, NULL, NULL, NULL),
        ('SH042', 'suzuki', '鈴木健一', CURRENT_DATE - 4, '17:00', '22:00', 'confirmed', NOW() - INTERVAL 4 DAY, NULL, NULL, NULL, NULL),
        ('SH043', 'ito', '伊藤優', CURRENT_DATE - 4, '10:00', '16:00', 'confirmed', NOW() - INTERVAL 4 DAY, NULL, NULL, NULL, NULL),
        ('SH044', 'takahashi', '高橋翔', CURRENT_DATE - 4, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 4 DAY, NULL, NULL, NULL, NULL),
        ('SH045', 'tanaka', '田中太郎', CURRENT_DATE - 3, '06:00', '15:00', 'confirmed', NOW() - INTERVAL 3 DAY, NULL, NULL, NULL, NULL),
        ('SH046', 'sato', '佐藤花子', CURRENT_DATE - 3, '09:00', '17:00', 'confirmed', NOW() - INTERVAL 3 DAY, NULL, NULL, NULL, NULL),
        ('SH047', 'yamada', '山田美咲', CURRENT_DATE - 3, '18:00', '22:00', 'confirmed', NOW() - INTERVAL 3 DAY, NULL, NULL, NULL, NULL),
        ('SH048', 'takahashi', '高橋翔', CURRENT_DATE - 3, '22:00', '06:00', 'confirmed', NOW() - INTERVAL 3 DAY, NULL, NULL, NULL, NULL),
        -- 週末（先週の土日）
        ('SH049', 'suzuki', '鈴木健一', CURRENT_DATE - 2, '10:00', '18:00', 'confirmed', NOW() - INTERVAL 2 DAY, NULL, NULL, NULL, NULL),
        ('SH050', 'watanabe', '渡辺リサ', CURRENT_DATE - 2, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 2 DAY, NULL, NULL, NULL, NULL),
        ('SH051', 'takahashi', '高橋翔', CURRENT_DATE - 2, '06:00', '14:00', 'confirmed', NOW() - INTERVAL 2 DAY, NULL, NULL, NULL, NULL),
        ('SH052', 'ito', '伊藤優', CURRENT_DATE - 2, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 2 DAY, NULL, NULL, NULL, NULL),
        ('SH053', 'suzuki', '鈴木健一', CURRENT_DATE - 1, '10:00', '18:00', 'confirmed', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NULL),
        ('SH054', 'watanabe', '渡辺リサ', CURRENT_DATE - 1, '14:00', '20:00', 'confirmed', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NULL),
        ('SH055', 'takahashi', '高橋翔', CURRENT_DATE - 1, '06:00', '14:00', 'confirmed', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL, NULL),
        -- 今日
        ('SH056', 'tanaka', '田中太郎', CURRENT_DATE, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH057', 'sato', '佐藤花子', CURRENT_DATE, '09:00', '17:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH058', 'watanabe', '渡辺リサ', CURRENT_DATE, '14:00', '20:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH059', 'yamada', '山田美咲', CURRENT_DATE, '18:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH060', 'takahashi', '高橋翔', CURRENT_DATE, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        -- 明日以降（未来2週間）
        ('SH061', 'tanaka', '田中太郎', CURRENT_DATE + 1, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH062', 'suzuki', '鈴木健一', CURRENT_DATE + 1, '17:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH063', 'ito', '伊藤優', CURRENT_DATE + 1, '10:00', '16:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH064', 'takahashi', '高橋翔', CURRENT_DATE + 1, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH065', 'tanaka', '田中太郎', CURRENT_DATE + 2, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH066', 'sato', '佐藤花子', CURRENT_DATE + 2, '09:00', '17:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH067', 'watanabe', '渡辺リサ', CURRENT_DATE + 2, '14:00', '20:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH068', 'yamada', '山田美咲', CURRENT_DATE + 2, '18:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH069', 'takahashi', '高橋翔', CURRENT_DATE + 2, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH070', 'tanaka', '田中太郎', CURRENT_DATE + 3, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH071', 'suzuki', '鈴木健一', CURRENT_DATE + 3, '17:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH072', 'ito', '伊藤優', CURRENT_DATE + 3, '10:00', '16:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH073', 'takahashi', '高橋翔', CURRENT_DATE + 3, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH074', 'tanaka', '田中太郎', CURRENT_DATE + 4, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH075', 'sato', '佐藤花子', CURRENT_DATE + 4, '09:00', '17:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH076', 'yamada', '山田美咲', CURRENT_DATE + 4, '18:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH077', 'takahashi', '高橋翔', CURRENT_DATE + 4, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        -- 次の週末
        ('SH078', 'suzuki', '鈴木健一', CURRENT_DATE + 5, '10:00', '18:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH079', 'watanabe', '渡辺リサ', CURRENT_DATE + 5, '14:00', '20:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH080', 'takahashi', '高橋翔', CURRENT_DATE + 5, '06:00', '14:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH081', 'ito', '伊藤優', CURRENT_DATE + 5, '14:00', '20:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH082', 'suzuki', '鈴木健一', CURRENT_DATE + 6, '10:00', '18:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH083', 'watanabe', '渡辺リサ', CURRENT_DATE + 6, '14:00', '20:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH084', 'takahashi', '高橋翔', CURRENT_DATE + 6, '06:00', '14:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        -- 再来週
        ('SH085', 'tanaka', '田中太郎', CURRENT_DATE + 7, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH086', 'sato', '佐藤花子', CURRENT_DATE + 7, '09:00', '17:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH087', 'yamada', '山田美咲', CURRENT_DATE + 7, '18:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH088', 'takahashi', '高橋翔', CURRENT_DATE + 7, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH089', 'tanaka', '田中太郎', CURRENT_DATE + 8, '06:00', '15:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH090', 'suzuki', '鈴木健一', CURRENT_DATE + 8, '17:00', '22:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH091', 'ito', '伊藤優', CURRENT_DATE + 8, '10:00', '16:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH092', 'takahashi', '高橋翔', CURRENT_DATE + 8, '22:00', '06:00', 'confirmed', NOW(), NULL, NULL, NULL, NULL),
        ('SH093', 'tanaka', '田中太郎', CURRENT_DATE + 9, '06:00', '15:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH094', 'sato', '佐藤花子', CURRENT_DATE + 9, '09:00', '17:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH095', 'watanabe', '渡辺リサ', CURRENT_DATE + 9, '14:00', '20:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH096', 'yamada', '山田美咲', CURRENT_DATE + 9, '18:00', '22:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH097', 'tanaka', '田中太郎', CURRENT_DATE + 10, '06:00', '15:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH098', 'suzuki', '鈴木健一', CURRENT_DATE + 10, '17:00', '22:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH099', 'ito', '伊藤優', CURRENT_DATE + 10, '10:00', '16:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH100', 'tanaka', '田中太郎', CURRENT_DATE + 11, '06:00', '15:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH101', 'sato', '佐藤花子', CURRENT_DATE + 11, '09:00', '17:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        ('SH102', 'yamada', '山田美咲', CURRENT_DATE + 11, '18:00', '22:00', 'pending', NOW(), NULL, NULL, NULL, NULL),
        -- キャンセルされたシフト例
        ('SH103', 'sato', '佐藤花子', CURRENT_DATE + 4, '14:00', '20:00', 'cancelled', NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 2 DAY, '子供の学校行事', NULL, NULL),
        ('SH104', 'suzuki', '鈴木健一', CURRENT_DATE - 4, '17:00', '22:00', 'cancelled', NOW() - INTERVAL 6 DAY, NOW() - INTERVAL 5 DAY, '体調不良', NULL, NULL),
        -- シフト交代例
        ('SH105', 'yamada', '山田美咲', CURRENT_DATE - 3, '14:00', '20:00', 'swapped', NOW() - INTERVAL 5 DAY, NULL, NULL, 'watanabe', NOW() - INTERVAL 4 DAY)
    """)

    # シフト交代リクエストのサンプルデータ
    conn.execute("""
        INSERT INTO swap_requests VALUES
        -- 承認済みの交代リクエスト（過去）
        ('SW001', 'SH105', 'yamada', '山田美咲', CURRENT_DATE - 3, '14:00', '20:00',
         '急用ができたため', 'approved', NOW() - INTERVAL 5 DAY, 'watanabe', '渡辺リサ', NOW() - INTERVAL 4 DAY),
        ('SW002', 'SH029', 'sato', '佐藤花子', CURRENT_DATE - 7, '09:00', '17:00',
         '子供が熱を出した', 'approved', NOW() - INTERVAL 8 DAY, 'ito', '伊藤優', NOW() - INTERVAL 7 DAY),
        ('SW003', 'SH014', 'suzuki', '鈴木健一', CURRENT_DATE - 11, '17:00', '22:00',
         '大学のテスト勉強', 'approved', NOW() - INTERVAL 12 DAY, 'yamada', '山田美咲', NOW() - INTERVAL 11 DAY),

        -- 却下された交代リクエスト
        ('SW004', 'SH033', 'suzuki', '鈴木健一', CURRENT_DATE - 6, '17:00', '22:00',
         '友人の誕生日', 'rejected', NOW() - INTERVAL 7 DAY, NULL, NULL, NULL),

        -- 現在ペンディング中の交代リクエスト
        ('SW005', 'SH068', 'yamada', '山田美咲', CURRENT_DATE + 2, '18:00', '22:00',
         'バイト面接があるため', 'pending', NOW() - INTERVAL 1 DAY, NULL, NULL, NULL),
        ('SW006', 'SH075', 'sato', '佐藤花子', CURRENT_DATE + 4, '09:00', '17:00',
         '病院の予約', 'pending', NOW(), NULL, NULL, NULL),
        ('SW007', 'SH087', 'yamada', '山田美咲', CURRENT_DATE + 7, '18:00', '22:00',
         '学校行事', 'pending', NOW(), NULL, NULL, NULL),

        -- 期限切れ（対応されなかった）
        ('SW008', 'SH019', 'yamada', '山田美咲', CURRENT_DATE - 10, '18:00', '22:00',
         '体調不良', 'expired', NOW() - INTERVAL 11 DAY, NULL, NULL, NULL)
    """)
