# Slide Deck — Context for Claude Code

## What This Is
Presentation for the **Dify Plugin Competition 2026**. 15-minute live presentation with demos.
Plugin: **からあげ店長クン** — a Dify agent plugin with 13 tools that automates convenience store manager tasks.

## Files
- `slide-deck-v2.html` — current working version (11 slides, 1024×576px each)
- `slide-deck.html` — original v1 (14 slides, don't touch)
- `speaker-script.md` — needs updating to match current v2 structure

## Core Messaging: "自分で考えて動く"
The key differentiator is **autonomous tool selection**. Most Dify competition entries are chatflows or RAG pipelines with fixed steps. This plugin uses **agent mode** — the LLM decides which tools to use and in what order at runtime, not the developer.

Frame it as: the agent thinks for itself. The developer builds the tools, the agent decides how to use them.

Yoichi will verbally acknowledge that agents aren't his original idea — he applied the concept to a real business domain with real working tools.

## Slide Tone Rules (IMPORTANT)
- **No LLM-sounding copy.** No marketing speak, no startup pitch aesthetics, no slogans.
- **No emoji decoration** on headers or list items.
- **No `.note` commentary boxes** that editorialize ("ここがポイント", "～を見せたかった"). If the slide content doesn't speak for itself, fix the content.
- **No repetitive grammar patterns** (noun + を + verb, noun + を + verb, noun + を + verb).
- **Tone: direct, factual, engineer-to-engineer.** Write as if explaining to a mid-level engineer at a competition, not pitching to VCs.
- **Japanese 資料文化**: high info density, orderly layouts, no huge empty space. Let the logic make the argument.
- **Concrete Lawson examples** over abstract statements. "「明日の発注を最適化して」→ 天気取得→需要予測→在庫確認→発注計算" is better than "自然言語で業務を実行".

## Competition Context
- **5 evaluation criteria**: 新規性、独自性、採算性、パフォーマンス、使いやすさ
- **Competitive differentiator**: Most entries are chatflows/RAG. This is an autonomous agent with 13 working tools. LLM reasons + chains tools without manual intervention.
- **No Q&A slide** (Japanese style — removed).
- **Demo early, demo long** — 3 live demos are the centerpiece.

## 11 Slide Structure
1. **Title** — からあげ店長クン, "自分で考えて、自分で動くAIエージェント"
2. **作ったもの** — What it does. Chatbot vs agent comparison (chatbot advises, agent executes)
3. **エージェントとは** — Chatflow (fixed steps) vs Agent (LLM picks tools). Concrete example.
4. **ツール構成** — 13 tools in 6 categories (sales/dashboard, shift, demand/ordering, inventory, LINE/items, infra)
5. **環境制約と対応** — 4 Dify Cloud constraints and workarounds (read-only FS, no cross-plugin comms, file output bug, API dependency)
6. **デモ① 売上ダッシュボード** — "今週の売上ダッシュボードを作って" → 3 tools chained → inline HTML output
7. **デモ② 天気連動の発注最適化** — "天気を見て明日の発注を最適化して" → 4 tools chained
8. **デモ③ 急な欠勤対応** — "田中さんが明日休み。シフト更新+LINE文作成" → 4 tools chained
9. **なぜコンビニ店長か** — Business context: ¥468万/store annual waste, 56K stores, experience-dependent ops
10. **まとめ** — "何が違うか / 何を作ったか" + tech stack + constraint workarounds
11. **APPENDIX インストール方法** — 4-step GitHub install + repo URL

## Technical Details
- All tools run on **DuckDB in-memory** (Dify Cloud FS is read-only)
- Only external API: **Open-Meteo** (free, no key) for weather
- ML: **RandomForest** for demand forecasting (runs on seed data)
- Output: **inline HTML** in chat (Dify's create_blob_message has a bug)
- 13 tools in 1 plugin (no cross-plugin data sharing in Dify)
- **107 unit tests**
- Plugin version: 0.3.2

## Screenshot Placeholders
Demo slides (6, 7, 8) have `<div class="ph">` placeholder boxes. These need actual Dify screenshots from Yoichi — don't remove them, just leave as-is or mark clearly.

## Speaker Script
`speaker-script.md` is outdated (written for a 14-slide version). Needs rewrite to match current 11-slide structure. Key points:
- Verbal framing: "agent isn't my invention, I applied it to real business tools"
- Demo-heavy: most time on slides 6-8
- Keep it natural, not scripted-sounding

## CSS Notes
- Slides are 1024×576px, Noto Sans JP font
- Print CSS included for PDF export
- Icon asset: `karaage-tencho-kun/_assets/icon.webp`
- Keep layout/CSS structure intact when editing content

## Author
尾嶋 洋一 (Yoichi Ojima)
