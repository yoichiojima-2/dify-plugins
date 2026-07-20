# dify-plugins

Monorepo for custom [Dify](https://dify.ai) plugins.

## Contents

- **[karaage-tencho-kun](karaage-tencho-kun/)** — proof-of-concept tool plugin: an AI assistant for convenience store operations (shift management, weather-based demand forecasting, inventory, sales analytics, and inline HTML dashboards). Python 3.12, tested with pytest.
- **slide-deck** — presentation material for the plugin demo.

## Development

```bash
# install dependencies and run tests
cd karaage-tencho-kun && uv sync && uv run pytest

# build the plugin package (requires the dify CLI)
make build   # -> build/karaage-tencho-kun.difypkg
```

## CI

- **Test** (`.github/workflows/test.yml`) — runs the pytest suite on every push and pull request to `main`.
- **Build** (`.github/workflows/build.yml`) — on a GitHub release, builds the `.difypkg`, updates the example app manifest with the new version/checksum, and uploads both as release assets.

## Releasing

1. Bump `version:` and `meta.version:` in `karaage-tencho-kun/manifest.yaml` (semver).
2. Commit, push, and create a GitHub release tagged `vX.Y.Z`.
3. CI builds and attaches `karaage-tencho-kun.difypkg` to the release.
