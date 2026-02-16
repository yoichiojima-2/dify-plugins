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
│   ├── shift_manager.*        # Shift management (SQL/DuckDB)
│   ├── shift_optimizer.*      # Shift optimization
│   ├── shift_table_generator.*# Shift table data (JSON)
│   ├── sales_analytics.*      # Sales analysis (SQL/DuckDB)
│   ├── dashboard_generator.*  # Dashboard data (JSON)
│   ├── dashboard_template.*   # Inline HTML templates for chat bubble rendering
│   ├── hourly_weather.*       # Weather forecast (Open-Meteo)
│   ├── demand_forecast.*      # ML demand prediction
│   ├── inventory_manager.*    # Inventory management
│   ├── line_composer.*        # LINE message generation
│   ├── lawson_items.*         # Product catalog
│   ├── datetime_utils.*       # JST conversion utilities
│   └── file_writer.*          # Create downloadable files (kept for backward compat, not in agent)
├── data/                      # Static data files
│   ├── dashboard_templates.json  # HTML templates for inline rendering
│   ├── line_templates.json
│   ├── inventory_manager_seed.json
│   ├── sales_analytics_seed.json
│   ├── shift_manager_seed.json
│   └── lawson_items.json
├── tests/                     # Unit tests
└── examples/                  # Dify app YAML
    ├── agent.yml              # PRIMARY: Agent-chat mode app
    └── chatflow.yml           # ARCHIVE: Chatflow mode (no longer primary)
```

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
| `file_writer` | Create downloadable files | N/A (kept but not in agent tools) |

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
