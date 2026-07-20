# karaage-tencho-kun（からあげ店長クン）

**Author:** yoichiojima
**Version:** 0.3.2
**Type:** tool

AI assistant plugin for [Dify](https://dify.ai) targeting convenience store operations — shift management, weather-based demand forecasting, inventory, sales analytics, and inline HTML dashboards rendered directly in the chat bubble. Built as a proof of concept around a fictional store scenario using bundled seed data.

## Tools

13 tools, defined in `tools/*.yaml` with implementations in `tools/*.py`:

- **hourly_weather** — hourly forecast via the Open-Meteo API (no API key required)
- **demand_forecast** — weather-based demand prediction (scikit-learn model in `models/`)
- **shift_manager / shift_optimizer / shift_table_generator** — staff shift management
- **inventory_manager / order_optimizer** — stock tracking and order recommendations
- **sales_analytics** — sales queries over in-memory DuckDB seed data
- **dashboard_generator / dashboard_template** — inline HTML dashboards for Dify chat
- **lawson_items / line_composer / datetime_utils** — product lookup, LINE-style messages, datetime helpers

Data is loaded from `data/*.json` into in-memory DuckDB (the Dify cloud filesystem is read-only), so the plugin needs no external database or credentials.

## Development

```bash
uv sync                 # install dependencies
uv run pytest           # run tests
```

From the repository root, `make build` packages the plugin into `build/karaage-tencho-kun.difypkg` (requires the `dify` CLI).

For remote debugging against a Dify instance, copy `.env.example` to `.env` and fill in the values, then `make run`.

## Example App

`examples/agent.yml` is an importable Dify agent app wired to this plugin. See the repository root README for release and install flow.
