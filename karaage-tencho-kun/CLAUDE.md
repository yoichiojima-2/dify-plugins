# karaage-tencho-kun

POC Dify plugin for Lawson convenience store operations assistant.

## Background

This project is a proof-of-concept Dify app called "からあげ店長クン" (Karaage Tencho-kun) that assists Lawson store managers with daily operations.

### Why a Custom Plugin?

The Dify cloud environment has significant limitations:
- Cannot use marketplace plugins that require API configuration
- Available built-in tools are limited (DuckDuckGo search, datetime, etc.)
- File system is read-only

To work around these constraints, this custom plugin bundles all necessary functionality:
- In-memory databases (DuckDB) for shift/sales data
- Mock external APIs (weather, product catalog)
- Utility functions (datetime conversion)

## Project Structure

```
├── manifest.yaml              # Plugin manifest
├── main.py                    # Entry point
├── provider/
│   └── karaage-tencho-kun.yaml/py   # Tool provider definition
├── tools/                     # Dify tools
│   ├── shift_manager.*        # Shift management (SQL/DuckDB)
│   ├── shift_optimizer.*      # Shift optimization
│   ├── shift_table_generator.*# HTML shift table generation
│   ├── sales_analytics.*      # Sales analysis (SQL/DuckDB)
│   ├── dashboard_generator.*  # HTML dashboard with Chart.js
│   ├── hourly_weather.*       # Weather forecast (Open-Meteo)
│   ├── demand_forecast.*      # ML demand prediction
│   ├── inventory_manager.*    # Inventory management (stock, expiration, orders)
│   ├── line_composer.*        # LINE message generation
│   ├── lawson_items.*         # Product catalog
│   ├── datetime_utils.*       # JST conversion utilities
│   ├── file_writer.*          # Create downloadable files (HTML, JSON, CSV, etc.)
│   └── get_file_url.*         # Get download URL from file object
├── data/                      # Static data files
│   ├── inventory_manager_seed.json
│   ├── line_templates.json
│   └── ...
├── tests/                     # Unit tests
└── examples/                  # Example Dify workflow YAML
```

## Tools

| Tool | Description | Implementation |
|------|-------------|----------------|
| `shift_manager` | SQL-based shift CRUD | In-memory DuckDB with sample staff/shifts |
| `shift_optimizer` | Auto-suggest optimal shifts | Uses shift_manager DB + demand prediction |
| `shift_table_generator` | Beautiful HTML shift tables | Weekly/daily/staff views with color coding |
| `sales_analytics` | Sales data analysis | In-memory DuckDB with sample sales data |
| `dashboard_generator` | HTML dashboards with Chart.js | Daily/weekly/comparison reports |
| `hourly_weather` | Weather forecast | Open-Meteo API (real weather) |
| `demand_forecast` | Demand prediction | ML model based on weather |
| `inventory_manager` | Inventory management | In-memory DuckDB with stock tracking, expiration alerts, order recommendations |
| `line_composer` | Generate LINE messages | Templates for staff communication |
| `lawson_items` | Product catalog search | Static JSON data |
| `datetime_utils` | Convert datetime to JST | Pure Python (zoneinfo) |
| `file_writer` | Create downloadable files | Returns blob message (use with get_file_url) |
| `get_file_url` | Get download URL from file | Extracts URL from file object for clickable links |

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

**Format:** Date-based versioning `YYYY.M.DD-N` (e.g., `2026.2.15-1`)
- `YYYY.M.DD` = date (month without leading zero)
- `-N` = division number (increment for multiple releases on same day)

**Release steps:**

1. **Bump version in `manifest.yaml`** (both `version:` and `meta.version:` fields)
2. **Commit and push**
3. **Create release:** `gh release create vYYYY.MMDD.N --title "vYYYY.MMDD.N" --notes "Release vYYYY.MMDD.N"`

The CI workflow (`.github/workflows/build.yml`) will automatically:
- Build the `.difypkg` package
- Update `examples/agent.yml`:
  - App name version (`name: 開発中_からあげ店長クン_vX.X.X`)
  - Plugin reference (`plugin_unique_identifier: ...`) with version and checksum
  - App version at end of file
- Commit the agent.yml changes
- Upload the package to the release

## Constraints

- **No external API calls** - All data is mocked or embedded
- **In-memory only** - Dify cloud has read-only filesystem
- **Single plugin** - Bundle everything to avoid marketplace dependencies

## Example Workflow

See `examples/開発中_からあげ店長クン.yml` for the full Dify workflow that uses this plugin. It includes:
- Question classifier routing to specialized agents
- Shift management agent
- Sales prediction agent (weather-based)
- Sales analysis agent with HTML report generation
- Complaint handling (RAG)
- Lawson company info (RAG)
- General conversation fallback
