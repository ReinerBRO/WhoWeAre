# WhoWeAre

**English** | **[日本語](README.ja.md)** | **[中文](README.md)**

Does your OpenClaw/Agent actually know you?

Most AI assistants know nothing about you when you first talk to them — they don't know what code you write, what games you play, or what music you listen to. Every time, you start from scratch. And their personalities are all the same: "I'm an AI assistant."

WhoWeAre fixes that.

Just drop a few links, and it extracts a complete user profile (`USER.md`) from your public pages, so your OpenClaw/Agent already knows you before the first message. Similarly, you can describe the Agent personality you want in one sentence, or simply name a character — anime, TV, historical, whatever — and the system will automatically generate matching identity and personality files.

## What It Does

- `/myprofile` → Scrapes your GitHub, Bilibili, Zhihu, and other profiles to synthesize an agent-consumable `USER.md`
- `/whoareu` → Generates `IDENTITY.md` (identity) + `SOUL.md` (personality) from a prompt, template, or character reference. For known characters, it auto-fetches Wikipedia data to build accurate persona files

Generated files are written to the OpenClaw workspace automatically. Existing files are backed up, never overwritten.

## Quick Start

```bash
git clone https://github.com/ReinerBRO/WhoWeAre.git
cd WhoWeAre
bash scripts/deploy-openclaw.sh
```

## Usage

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

Supported platforms:

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

### /whoareu — Define the Agent's Persona

```text
/whoareu A cyber ghost named Sayo, sharp-tongued but kind, values privacy
/whoareu template otaku
/whoareu reference Jarvis
/whoareu reference Jarvis --lang en       # English output
/whoareu template otaku --lang ja         # Japanese output
```

## Project Structure

```
llmkit/                      # Shared config + workspace path resolution
whoami/                      # Link scraping & USER.md synthesis
whoareu/                     # Persona generation (IDENTITY.md + SOUL.md)
openclaw-whoweare-plugin/    # OpenClaw plugin
```

## License

MIT
