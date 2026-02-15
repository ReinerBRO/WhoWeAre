# WhoWeAre

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**[English](README.en.md)** | **[日本語](README.ja.md)** | **中文**

> [OpenClaw](https://github.com/openclaw/openclaw) 插件 — 让你的 Agent 在第一句话之前就认识你，并拥有独一无二的灵魂。

丢几个链接，自动生成你的用户画像；说一个名字，自动生成 Agent 的身份与性格。告别千篇一律的"我是一个 AI 助手"。

## ✨ 特性

- 🔗 **链接即画像** — 丢入 GitHub / B站 / 知乎等链接，自动抓取并合成 `USER.md`
- 🎭 **一句话造人格** — 描述性格、指定模板、或直接说一个角色名，生成 `IDENTITY.md` + `SOUL.md`
- 🌐 **13+ 平台** — GitHub、GitLab、B站、知乎、微博、豆瓣、Steam、Reddit 等
- 🔍 **角色参照** — 输入"贾维斯""平泽唯""初音未来"等已知角色，自动检索维基百科 / 萌娘百科生成设定
- 🌍 **多语言** — 支持中文 / 英文 / 日文输出
- 💾 **安全写入** — 自动写入 OpenClaw workspace，已有文件自动备份不覆盖

## 📸 Demo

### USER.md 生成示例

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

### IDENTITY.md + SOUL.md 生成示例（`/whoareu reference 贾维斯`）

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

## 🚀 一键部署

```bash
git clone https://github.com/ReinerBRO/WhoWeAre.git
cd WhoWeAre
bash scripts/deploy-openclaw.sh
```

## 📖 使用

在 OpenClaw TUI 或任何接入了 OpenClaw 的聊天平台（Telegram、QQ、WhatsApp 等）中直接发送命令。

### /myprofile — 告诉 Agent 你是谁

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile run
```

也可以一步到位：

```text
/myprofile run https://github.com/<you> https://space.bilibili.com/<id>
```

其他命令：`list`、`clear`、`help`。

`--lang` 指定输出语言（默认中文）：

```text
/myprofile run --lang en    # 英文
/myprofile run --lang ja    # 日文
/myprofile run --lang zh    # 中文（默认）
```

<details>
<summary>支持 13+ 平台（点击展开）</summary>

| | 平台 | 链接格式 |
|:---:|:---|:---|
| <img src="https://cdn.simpleicons.org/github" width="16"> | GitHub | `https://github.com/<user>` |
| <img src="https://cdn.simpleicons.org/gitlab" width="16"> | GitLab | `https://gitlab.com/<user>` |
| <img src="https://cdn.simpleicons.org/bilibili" width="16"> | Bilibili | `https://space.bilibili.com/<uid>` |
| <img src="https://cdn.simpleicons.org/zhihu" width="16"> | 知乎 | `https://zhihu.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/sinaweibo" width="16"> | 微博 | `https://weibo.com/<uid>` |
| <img src="https://cdn.simpleicons.org/douban" width="16"> | 豆瓣 | `https://douban.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/googlescholar" width="16"> | Google Scholar | `https://scholar.google.com/citations?user=<id>` |
| <img src="https://cdn.simpleicons.org/xiaohongshu" width="16"> | 小红书 | `https://xiaohongshu.com/user/profile/<id>` |
| <img src="https://cdn.simpleicons.org/stackoverflow" width="16"> | Stack Overflow | `https://stackoverflow.com/users/<id>` |
| <img src="https://cdn.simpleicons.org/reddit" width="16"> | Reddit | `https://reddit.com/user/<name>` |
| <img src="https://cdn.simpleicons.org/steam" width="16"> | Steam | `https://steamcommunity.com/id/<name>` |
| <img src="https://cdn.simpleicons.org/medium" width="16"> | Medium | `https://medium.com/@<user>` |
| <img src="https://cdn.simpleicons.org/devdotto" width="16"> | Dev.to | `https://dev.to/<user>` |
| 🌐 | 其他网页 | 任意 URL |

</details>

### /whoareu — 定义 Agent 的人格

```text
/whoareu reference 平泽唯
/whoareu reference 平泽唯 --lang en    # 英文输出
/whoareu template otaku
/whoareu template otaku --lang ja      # 日文输出
/whoareu 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
```

## 📁 项目结构

```
llmkit/                      # 共享配置 + workspace 路径解析
whoami/                      # 链接抓取与 USER.md 合成
whoareu/                     # 人格生成（IDENTITY.md + SOUL.md）
openclaw-whoweare-plugin/    # OpenClaw 插件
```

## License

MIT
