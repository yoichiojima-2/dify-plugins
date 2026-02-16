# karaage-tencho-kun

POC Dify plugin for Lawson convenience store operations assistant.

## Architecture: Agent-Only with Inline HTML

This plugin uses **agent-chat mode** (`examples/agent.yml`) as the primary deployment. Dashboards and reports are rendered directly in the Dify chat bubble using inline HTML/CSS — no file downloads needed.

### Dashboard Rendering Flow
1. Data tool (dashboard_generator, shift_table_generator, sales_analytics) returns JSON
2. `dashboard_template` tool returns an HTML template with `{{PLACEHOLDER}}` markers
3. LLM fills placeholders with actual data from step 1
4. LLM outputs the completed HTML directly as a chat message
5. Dify renders the HTML inline in the chat bubble

### Why Not Chatflow?
- Chatflow pipeline (Agent → Classifier → LLM → save_file → download URL) was complex and flaky
- Agent nodes don't forward `create_blob_message()` files (Dify bug)
- Inline HTML rendering eliminates the need for file downloads entirely

## Project Structure

```
├── manifest.yaml              # Plugin manifest + version
├── main.py                    # Entry point
├── provider/
│   └── karaage-tencho-kun.yaml/py   # Tool provider definition
├── tools/                     # Dify tools
│   ├── db_utils.py            # 共有: DuckDBManager (接続・シードデータ管理)
│   ├── data_loader.py         # 共有: CachedJSONLoader (JSON読み込み・キャッシュ)
│   ├── datetime_utils.*       # 共有: JST変換, 曜日定数, 日付フォーマット
│   ├── shift_manager.*        # シフト管理 (SQL/DuckDB)
│   ├── shift_optimizer.*      # シフト最適化
│   ├── shift_table_generator.*# シフト表データ (JSON)
│   ├── sales_analytics.*      # 売上分析 (SQL/DuckDB)
│   ├── dashboard_generator.*  # ダッシュボードデータ (JSON)
│   ├── dashboard_template.*   # インラインHTMLテンプレート
│   ├── hourly_weather.*       # 天気予報 (Open-Meteo API)
│   ├── demand_forecast.*      # 需要予測 (MLモデル)
│   ├── inventory_manager.*    # 在庫管理
│   ├── line_composer.*        # LINEメッセージ生成
│   └── lawson_items.*         # 商品カタログ
├── data/                      # 静的データファイル
│   ├── dashboard_templates.json  # インラインHTMLテンプレート
│   ├── line_templates.json
│   ├── inventory_manager_seed.json
│   ├── sales_analytics_seed.json
│   ├── shift_manager_seed.json
│   └── lawson_items.json
├── tests/                     # ユニットテスト (107件)
└── examples/                  # Dify アプリYAML
    ├── agent.yml              # PRIMARY: エージェントモード
    └── chatflow.yml           # ARCHIVE: チャットフロー (非推奨)
```

## Shared Utilities (共有ユーティリティ)

### `tools/db_utils.py` — DuckDBManager
DuckDBインメモリ接続とシードデータのキャッシュを一元管理するクラス。
使用元: `sales_analytics`, `shift_manager`, `inventory_manager`

```python
from tools.db_utils import DuckDBManager
_db = DuckDBManager("seed_file.json", _init_schema)
conn = _db.get_connection()     # 初回にスキーマ初期化
seed = _db.load_seed_data()     # JSONキャッシュ読み込み
_db.reset()                     # テスト用リセット
```

### `tools/data_loader.py` — CachedJSONLoader
静的JSONファイルの読み込みとキャッシュを管理するクラス。
使用元: `lawson_items`, `line_composer`, `dashboard_template`

```python
from tools.data_loader import CachedJSONLoader
_loader = CachedJSONLoader("data_file.json")
data = _loader.load()           # JSONキャッシュ読み込み
path = _loader.file_path        # ファイルパス取得
_loader.reset()                 # テスト用リセット
```

### `tools/datetime_utils.py` — 共有定数 & ユーティリティ
複数ツールで共通利用する日付関連の定数・関数。

| Export | 説明 |
|--------|------|
| `JST` | `ZoneInfo("Asia/Tokyo")` |
| `WEEKDAY_JA` | `["月", "火", ..., "日"]` (月曜始まり, weekday()対応) |
| `WEEKDAY_JA_SUN_START` | `["日", "月", ..., "土"]` (日曜始まり, DOW対応) |
| `WEEKDAY_KEYS` | `["mon", "tue", ..., "sun"]` (availability JSON用) |
| `get_weekday_ja(date_str)` | 日付文字列→日本語曜日 |
| `format_date_ja(date_str)` | 日付文字列→`"M/D"`形式 |
| `parse_expires_at(v, now)` | 消費期限パース (str/datetime両対応) |

## Tools

| Tool | Description | Data Source |
|------|-------------|-------------|
| `shift_manager` | SQL-based shift CRUD | In-memory DuckDB |
| `shift_optimizer` | Auto-suggest optimal shifts | DuckDB + demand model |
| `shift_table_generator` | Shift data as JSON | DuckDB |
| `sales_analytics` | Sales data analysis via SQL | In-memory DuckDB |
| `dashboard_generator` | Dashboard data as JSON (daily/weekly/comparison) | DuckDB |
| `dashboard_template` | Inline HTML/CSS templates for chat bubble rendering | Static JSON |
| `hourly_weather` | Weather forecast | Open-Meteo API |
| `demand_forecast` | Demand prediction | ML model |
| `inventory_manager` | Inventory management | In-memory DuckDB |
| `line_composer` | Generate LINE messages | Static templates |
| `lawson_items` | Product catalog search | Static JSON |
| `datetime_utils` | Convert datetime to JST | Pure Python |


## Inline HTML Constraints (Quick Reference)

- All styles via `style="..."` — no `<style>` blocks, no `class=`
- No `<p>` tags — use `<div>`
- No empty lines in HTML (breaks Dify rendering)
- No `<script>`, `<iframe>`, `<html>`, `<body>`
- Bar charts: `<div>` with percentage `width`/`height`
- Layout: `display:flex` (preferred) or `display:grid`
- Dark theme: bg `#1a1a2e`, cards `#16213e`, borders `#0f3460`

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Package plugin (from parent dify-plugins directory)
cd .. && make build
# Output: build/karaage-tencho-kun.difypkg
```

## Versioning

**Format:** Date-based `YYYY.M.DD-N` (e.g., `2026.2.16-1`)

**Release steps:**
1. Bump version in `manifest.yaml` (both `version:` and `meta.version:`)
2. Commit and push
3. Create release: `gh release create vYYYY.M.DD-N --title "vYYYY.M.DD-N" --notes "..."`

CI auto-builds `.difypkg`, updates `examples/agent.yml` references, and uploads to release.

## Constraints

- **No external API calls** except Open-Meteo (free weather) — all other data is embedded
- **In-memory only** — Dify cloud has read-only filesystem
- **Single plugin** — Bundle everything to avoid marketplace dependencies
