# dify-plugins

Monorepo for Dify custom plugins. Currently contains one plugin: `karaage-tencho-kun`.

## Repository Structure

```
dify-plugins/
├── CLAUDE.md              # This file (repo-level context)
├── Makefile               # Build commands
├── .gitignore
├── .github/workflows/     # CI: build + release
├── karaage-tencho-kun/    # Plugin source
│   ├── CLAUDE.md          # Plugin-specific context
│   ├── manifest.yaml      # Plugin metadata + version
│   ├── main.py            # Entry point
│   ├── provider/          # Tool provider YAML + Python
│   ├── tools/             # All tool implementations
│   ├── data/              # Static JSON data files
│   ├── tests/             # Unit tests
│   └── examples/          # Dify app YAML (agent.yml, chatflow.yml)
└── build/                 # Build output (.difypkg)
```

## Dify Platform Knowledge

### App YAML Import Requirements
- App `version:` must be **semver** (e.g., `0.6.0`), NOT date-based
- Dependency type for GitHub plugins: `type: github` (not `type: package`)
- Unicode: use literal emojis in YAML, not `\U0001F916`

### Inline HTML Rendering in Chat Bubbles
Dify renders inline HTML/CSS directly in chat bubbles (both agent-chat and chatflow modes). This is the primary rendering method for dashboards and reports.

**Allowed:**
- `<div>`, `<span>`, `<strong>`, `<em>`, `<br>`, `<hr>`
- `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`
- `<h1>`-`<h6>`, `<details>`, `<summary>`
- `<button data-message="...">`, `<form data-format="json">`
- Inline `style="..."` on most tags
- `display:flex`, `display:grid`
- SVG inline

**Blocked (disallowedElements in Dify source markdown.tsx):**
- `<html>`, `<body>`, `<head>`, `<meta>`, `<link>`
- `<style>` blocks, `<script>`, `<iframe>`
- `<p>` with inline styles (use `<div>` instead)
- `class=` / `className=` attributes
- JavaScript event handlers (onclick, onload, etc.)
- External fonts (Google Fonts CDN)
- Empty lines inside HTML blocks (breaks Markdown parsing)

**CSS-only bar charts:** Use `<div>` with percentage-based `width` or `height` and `background-color`.

### Chatflow Limitations (reference only - not primary mode)
- Agent nodes do NOT forward `create_blob_message()` files to output (Dify bug)
- Standalone Tool nodes require the DifySandbox service
- If sandbox crashes, Code/Template nodes fail

### Sandbox Service
- Code nodes and Template Transform (Jinja2) require DifySandbox
- Common crash: missing `conf/config.yaml` in `dify/docker/volumes/sandbox/conf/`

### credentials_for_provider Format
Must be a **dict** keyed by credential name, NOT a list.

## Development Workflow

### Prerequisites
- Python 3.12+, uv, dify CLI, gh CLI
- Working directory for tests: `karaage-tencho-kun/`

### Commands
```bash
# Install dependencies
cd karaage-tencho-kun && uv sync

# Run tests
cd karaage-tencho-kun && uv run pytest

# Build plugin package
make build
# Output: build/karaage-tencho-kun.difypkg

# Create release
gh release create vX.Y.Z --title "vX.Y.Z" --notes "Release notes"
```

### Release Process
1. Bump version in `karaage-tencho-kun/manifest.yaml` (both `version:` and `meta.version:`)
2. Commit and push
3. Create git tag and GitHub release
4. CI auto-builds `.difypkg`, uploads to release, and updates `examples/agent.yml` with new plugin reference

**Version format:** Standard semver `MAJOR.MINOR.PATCH` (e.g., `0.1.0`, `0.2.0`, `1.0.0`)
**Tag format:** `vX.Y.Z` (e.g., `v0.1.0`)
**Note:** Do NOT use date-based versions or pre-release suffixes (e.g., `-1`) — Dify treats them as older versions.

**Note:** CI auto-updates `examples/agent.yml` after release — pull before next push.

## Updating Plugin in Dify UI

1. Go to `localhost/plugins` (or cloud.dify.ai/plugins)
2. Find plugin card → click refresh/update icon
3. Select latest version tag + `.difypkg` package
4. Click Next → Install
- Cannot reinstall same version (must bump)
- Tag must have valid `.difypkg` release asset

## Importing/Updating App in Dify UI

1. Go to Studio (`localhost/apps`)
2. Delete old app if updating (cannot overwrite)
3. Import DSL file → From URL tab
4. Paste raw GitHub URL:
   - Agent: `https://raw.githubusercontent.com/yoichiojima-2/dify-plugins/refs/heads/main/karaage-tencho-kun/examples/agent.yml`
5. Create → Preview to test

For Docker-hosted Dify accessing local files:
```bash
cd karaage-tencho-kun/examples && python3 -m http.server 8899
# Import from: http://host.docker.internal:8899/agent.yml
```
