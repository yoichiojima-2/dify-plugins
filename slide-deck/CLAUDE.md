# Slide Deck — Context for Claude Code

## What This Is
Presentation for the **Dify Plugin Competition 2026**. 15-minute live presentation with recorded demo videos.
Plugin: **からあげ店長クン** — a Dify agent plugin with 13 tools that automates convenience store manager tasks.

## Files
- `slide-deck.html` — current working version (10 slides, 1024×576px, presentation mode with keyboard nav)
- `speaker-script.md` — matches slide structure, 15-min timing with demo video cues
- `demos/2x/` — recorded demo videos (2x speed) for playback during presentation
- `agent-explainer.svg` — agent vs chatflow visualization (banana smoothie theme)

## Presentation Mode
- Press **F** to enter/exit fullscreen presentation mode
- **← →** / **↑ ↓** / **Space** to navigate slides
- **Home** / **End** to jump to first/last slide
- **Esc** to exit presentation mode
- Slide counter auto-shows on mouse move, fades after 2s

## Demo Videos (demos/2x/)
- `売上ダッシュボード作成と深掘分析.mp4` → Slide 6
- `天気による需要予測と在庫最適化.mp4` → Slide 7
- `シフト管理.mp4` → Slide 8
- `消費期限の近い商品を探す.mp4` (not used in slides, backup)
- `プラグインインストール方法.mp4` (not used in slides, backup)

## Core Messaging: "開発者はツールを作る。どう使うかはLLMが決める。"
The key differentiator is **autonomous tool selection**. Most Dify competition entries are chatflows or RAG pipelines with fixed steps. This plugin uses **agent mode** — the LLM decides which tools to use and in what order at runtime, not the developer.

Frame it as: the developer builds the tools, the LLM decides how to use them.

Yoichi will verbally acknowledge that agents aren't his original idea — he applied the concept to a real business domain with real working tools.

## Slide Tone Rules (IMPORTANT)
- **No LLM-sounding copy.** No marketing speak, no startup pitch aesthetics, no slogans.
- **No emoji decoration** on headers or list items.
- **No repetitive grammar patterns** (noun + を + verb, noun + を + verb, noun + を + verb).
- **Tone: direct, factual, engineer-to-engineer.** Write as if explaining to a mid-level engineer at a competition, not pitching to VCs.
- **話す資料 (speaker support), not 読む資料 (reading material).** Slides contain minimal text — the speaker fills in the detail verbally.
- **Concrete Lawson examples** over abstract statements. "「明日の発注を最適化して」→ 天気取得→需要予測→在庫確認→発注計算" is better than "自然言語で業務を実行".

## Competition Context
- **5 evaluation criteria**: 新規性、独自性、採算性、パフォーマンス、使いやすさ
- **Competitive differentiator**: Most entries are chatflows/RAG. This is an autonomous agent with 13 working tools. LLM reasons + chains tools without manual intervention.
- **No Q&A slide** (Japanese style — removed).
- **Demo early, demo long** — 3 recorded demos are the centerpiece.

## 10 Slide Structure
1. **Title** — からあげ店長クン, "自分で考えて、自分で動くAIエージェント"
2. **なぜコンビニ店長か** — 468万円/56,000店 + one-line bullets (why this domain)
3. **作ったもの** — Chatbot vs agent comparison (short phrases)
4. **エージェントとは** — Chatflow vs Agent flow diagrams + concrete example
5. **ツール構成** — 13 tools in 6 categories (names only, no descriptions)
6. **デモ① 売上ダッシュボード** — Prompt + tool chain + video cue
7. **デモ② 天気連動の発注最適化** — Prompt + tool chain + video cue
8. **デモ③ 急な欠勤対応** — Prompt + tool chain + video cue
9. **まとめ** — Key insight + capability chips + compact tech stack
10. **APPENDIX インストール方法** — 4-step GitHub install + repo URL

## Technical Details
- All tools run on **DuckDB in-memory** (Dify Cloud FS is read-only)
- Only external API: **Open-Meteo** (free, no key) for weather
- ML: **RandomForest** for demand forecasting (runs on seed data)
- Output: **inline HTML** in chat (Dify's create_blob_message has a bug)
- 13 tools in 1 plugin (no cross-plugin data sharing in Dify)
- **107 unit tests**
- Plugin version: 0.3.2

## CSS Notes
- Slides are 1024×576px, Noto Sans JP + IBM Plex Mono fonts, body font-size 15px
- Primary color: karaage orange (#d97706, #f59e0b, dark: #92400e)
- Secondary color: Lawson blue (#005bac, #0068b7)
- Warm paper background (#fefcf9), orange top accent stripes on content slides
- Dark cinematic areas for demo video placeholders
- Dark split-layout まとめ slide
- `font-feature-settings: 'palt'` for Japanese proportional alternates
- Presentation mode JS: keyboard nav + fullscreen scaling
- Icon asset: `../karaage-tencho-kun/_assets/icon.webp`
- Keep layout/CSS structure intact when editing content

## Author
尾嶋 洋一 (Yoichi Ojima)
