# WhoWeAre

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**English** | **[日本語](README.ja.md)** | **[中文](README.md)**

> Let AI know you before the first message. Give your Agent a soul.

Drop a few links, get a complete user profile. Name a character, get a full persona. No more "I'm an AI assistant."

## ✨ Features

- 🔗 **Links to Profile** — Drop GitHub / Bilibili / Zhihu links, auto-scrape and synthesize `USER.md`
- 🎭 **One-Line Persona** — Describe a personality, pick a template, or name a character to generate `IDENTITY.md` + `SOUL.md`
- 🌐 **13+ Platforms** — GitHub, GitLab, Bilibili, Zhihu, Weibo, Douban, Steam, Reddit, and more
- 🔍 **Character Reference** — Enter "Jarvis", "Hatsune Miku", etc. — auto-fetches Wikipedia to build the persona
- 🌍 **Multilingual** — Output in Chinese / English / Japanese
- 💾 **Safe Writes** — Auto-writes to OpenClaw workspace, existing files are backed up, never overwritten

## 📸 Demo

### USER.md Output Sample

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

### IDENTITY.md + SOUL.md Output Sample (`/whoareu reference Jarvis`)

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

## 🚀 Quick Start

```bash
git clone https://github.com/ReinerBRO/WhoWeAre.git
cd WhoWeAre
bash scripts/deploy-openclaw.sh
```

## 📖 Usage

Send commands directly in OpenClaw TUI or any platform connected to OpenClaw (Telegram, QQ, WhatsApp, etc.).

### /myprofile — Tell the Agent Who You Are

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile run
```

Or do it in one step:

```text
/myprofile run https://github.com/<you> https://space.bilibili.com/<id>
```

Other commands: `list`, `clear`, `help`.

`--lang` sets the output language (default: Chinese):

```text
/myprofile run --lang en    # English
/myprofile run --lang ja    # Japanese
/myprofile run --lang zh    # Chinese (default)
```

<details>
<summary>13+ Supported Platforms (click to expand)</summary>

| | Platform | Link Format |
|:---:|:---|:---|
| <img src="https://cdn.simpleicons.org/github" width="16"> | GitHub | `https://github.com/<user>` |
| <img src="https://cdn.simpleicons.org/gitlab" width="16"> | GitLab | `https://gitlab.com/<user>` |
| <img src="https://cdn.simpleicons.org/bilibili" width="16"> | Bilibili | `https://space.bilibili.com/<uid>` |
| <img src="https://cdn.simpleicons.org/zhihu" width="16"> | Zhihu | `https://zhihu.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/sinaweibo" width="16"> | Weibo | `https://weibo.com/<uid>` |
| <img src="https://cdn.simpleicons.org/douban" width="16"> | Douban | `https://douban.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/googlescholar" width="16"> | Google Scholar | `https://scholar.google.com/citations?user=<id>` |
| <img src="https://cdn.simpleicons.org/xiaohongshu" width="16"> | Xiaohongshu | `https://xiaohongshu.com/user/profile/<id>` |
| <img src="https://cdn.simpleicons.org/stackoverflow" width="16"> | Stack Overflow | `https://stackoverflow.com/users/<id>` |
| <img src="https://cdn.simpleicons.org/reddit" width="16"> | Reddit | `https://reddit.com/user/<name>` |
| <img src="https://cdn.simpleicons.org/steam" width="16"> | Steam | `https://steamcommunity.com/id/<name>` |
| <img src="https://cdn.simpleicons.org/medium" width="16"> | Medium | `https://medium.com/@<user>` |
| <img src="https://cdn.simpleicons.org/devdotto" width="16"> | Dev.to | `https://dev.to/<user>` |
| 🌐 | Any webpage | Any URL |

</details>

### /whoareu — Define the Agent's Persona

```text
/whoareu reference Jarvis
/whoareu reference Jarvis --lang en       # English output
/whoareu template otaku
/whoareu template otaku --lang ja         # Japanese output
/whoareu A cyber ghost named Sayo, sharp-tongued but kind, values privacy
```

## 📁 Project Structure

```
llmkit/                      # Shared config + workspace path resolution
whoami/                      # Link scraping & USER.md synthesis
whoareu/                     # Persona generation (IDENTITY.md + SOUL.md)
openclaw-whoweare-plugin/    # OpenClaw plugin
```

## License

MIT
