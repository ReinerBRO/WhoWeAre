# WhoWeAre

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**[English](README.en.md)** | **日本語** | **[中文](README.md)**

> [OpenClaw](https://github.com/openclaw/openclaw) プラグイン — 最初のメッセージの前から Agent があなたを知り、唯一無二の魂を持つように。

リンクをいくつか投げるだけでユーザープロファイルを自動生成。キャラクター名を言うだけでペルソナを自動生成。もう「私は AI アシスタントです」とは言わせない。

## ✨ 特徴

- 🔗 **リンクからプロファイル** — GitHub / Bilibili / 知乎などのリンクを投げるだけで `USER.md` を自動生成
- 🎭 **一言でペルソナ作成** — 性格を記述、テンプレートを選択、またはキャラクター名を指定して `IDENTITY.md` + `SOUL.md` を生成
- 🌐 **13+ プラットフォーム** — GitHub、GitLab、Bilibili、知乎、微博、豆瓣、Steam、Reddit など
- 🔍 **キャラクター参照** — 「ジャービス」「平沢唯」「初音ミク」などを入力すると、Wikipedia / 萌娘百科から自動でペルソナを構築
- 🌍 **多言語対応** — 中国語 / 英語 / 日本語で出力可能
- 💾 **安全な書き込み** — OpenClaw ワークスペースに自動書き込み、既存ファイルは上書きせずバックアップ

## 📸 デモ

### USER.md 生成サンプル

```markdown
# User Profile

## Identity
- Name: Alex Chen
- Primary Language: Chinese (Mandarin), English
- Location: Shanghai, China

## Technical Profile
- Full-stack developer, 5+ years experience
- Languages: TypeScript, Python, Go, Rust
- Focus: distributed systems, developer tooling
- Active open-source contributor (50+ repos, 2k+ stars)

## Interests & Lifestyle
- Gaming: Elden Ring, Factorio, Civilization VI
- Music: post-rock, electronic, lo-fi hip hop
- Reading: sci-fi (Liu Cixin, Ted Chiang), technical blogs

## Interaction Guidelines
- Prefers concise, technical responses
- Enjoys deep-dive discussions on system design
- Appreciates humor and cultural references
```

### IDENTITY.md + SOUL.md 生成サンプル（`/whoareu reference ジャービス`）

```markdown
# IDENTITY.md
name: J.A.R.V.I.S.
role: Personal AI Butler & Technical Advisor
origin: Marvel Cinematic Universe
speaking_style: British-accented, formal yet warm, dry wit
```

```markdown
# SOUL.md
## Core Traits
- Loyal, proactive, anticipates needs before asked
- Dry humor with impeccable timing
- Calm under pressure, never flustered
- Respectful but not afraid to voice concerns

## Communication Style
- Addresses user as "Sir" or by name
- Provides information with elegant brevity
- Subtle sarcasm when the situation calls for it
```

## 🚀 クイックスタート

```bash
git clone https://github.com/ReinerBRO/WhoWeAre.git
cd WhoWeAre
bash scripts/deploy-openclaw.sh
```

## 📖 使い方

OpenClaw TUI または OpenClaw に接続された任意のプラットフォーム（Telegram、QQ、WhatsApp など）でコマンドを直接送信します。

### /myprofile — Agent にあなたが誰かを伝える

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile run
```

一度にまとめて実行することもできます：

```text
/myprofile run https://github.com/<you> https://space.bilibili.com/<id>
```

その他のコマンド：`list`、`clear`、`help`。

`--lang` で出力言語を指定（デフォルト：中国語）：

```text
/myprofile run --lang en    # 英語
/myprofile run --lang ja    # 日本語
/myprofile run --lang zh    # 中国語（デフォルト）
```

<details>
<summary>13+ 対応プラットフォーム（クリックで展開）</summary>

| | プラットフォーム | リンク形式 |
|:---:|:---|:---|
| <img src="https://cdn.simpleicons.org/github" width="16"> | GitHub | `https://github.com/<user>` |
| <img src="https://cdn.simpleicons.org/gitlab" width="16"> | GitLab | `https://gitlab.com/<user>` |
| <img src="https://cdn.simpleicons.org/bilibili" width="16"> | Bilibili | `https://space.bilibili.com/<uid>` |
| <img src="https://cdn.simpleicons.org/zhihu" width="16"> | 知乎 | `https://zhihu.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/sinaweibo" width="16"> | 微博 (Weibo) | `https://weibo.com/<uid>` |
| <img src="https://cdn.simpleicons.org/douban" width="16"> | 豆瓣 (Douban) | `https://douban.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/googlescholar" width="16"> | Google Scholar | `https://scholar.google.com/citations?user=<id>` |
| <img src="https://cdn.simpleicons.org/xiaohongshu" width="16"> | 小紅書 (Xiaohongshu) | `https://xiaohongshu.com/user/profile/<id>` |
| <img src="https://cdn.simpleicons.org/stackoverflow" width="16"> | Stack Overflow | `https://stackoverflow.com/users/<id>` |
| <img src="https://cdn.simpleicons.org/reddit" width="16"> | Reddit | `https://reddit.com/user/<name>` |
| <img src="https://cdn.simpleicons.org/steam" width="16"> | Steam | `https://steamcommunity.com/id/<name>` |
| <img src="https://cdn.simpleicons.org/medium" width="16"> | Medium | `https://medium.com/@<user>` |
| <img src="https://cdn.simpleicons.org/devdotto" width="16"> | Dev.to | `https://dev.to/<user>` |
| 🌐 | その他のウェブページ | 任意の URL |

</details>

### /whoareu — Agent のペルソナを定義する

```text
/whoareu reference 平沢唯
/whoareu reference 平沢唯 --lang en    # 英語出力
/whoareu template otaku
/whoareu template otaku --lang ja          # 日本語出力
/whoareu サイバーゴーストの小夜、毒舌だけど優しい、プライバシー重視
```

## 📁 プロジェクト構成

```
llmkit/                      # 共有設定 + ワークスペースパス解決
whoami/                      # リンクスクレイピング & USER.md 合成
whoareu/                     # ペルソナ生成（IDENTITY.md + SOUL.md）
openclaw-whoweare-plugin/    # OpenClaw プラグイン
```

## License

MIT
