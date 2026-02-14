# OpenClaw WhoWeAre Plugin

Use `/myprofile` and `/whoareu` directly from OpenClaw commands.

## What this plugin does

- Adds `/myprofile` command:
  - queue links (`add`, `addmany`, `list`, `clear`)
  - run scraping + synthesis and write `USER.md`
- Adds `/whoareu` command:
  - generate `AGENTS.md`, `SOUL.md`, `IDENTITY.md` from prompt/template/reference

The plugin does not duplicate your Python logic. It invokes:

- `python -m whoami.cli`
- `python -m whoareu.cli`

## Install (local path)

From `WhoWeAre` repository root:

```bash
openclaw plugins install -l ./openclaw-whoweare-plugin
```

Then restart the gateway.

## Required project layout (default)

By default, plugin assumes:

- `./whoami` and `./whoareu` (standalone WhoWeAre repo)
- or `./whoweare/whoami` and `./whoweare/whoareu` (vendored inside another repo)

You can override these in plugin config:

- `plugins.entries.openclaw-whoweare.config.whoamiProjectDir`
- `plugins.entries.openclaw-whoweare.config.whoareuProjectDir`

## Python dependencies

Each project must be runnable in its own directory.

Example:

```bash
cd whoami && python3 -m pip install -e .
cd ../whoareu && python3 -m pip install -e .
```

If a `.venv` exists in each project, the plugin uses it automatically.

## Command usage

### myprofile (many links workflow)

```text
/myprofile add https://github.com/xxx
/myprofile add https://space.bilibili.com/xxx
/myprofile list
/myprofile run
```

Direct run without queue:

```text
/myprofile run https://github.com/xxx https://www.zhihu.com/people/xxx
```

Optional run flags:

```text
/myprofile run --provider openai --model gpt-4o --keep-queue
/myprofile run --no-llm
```

Alias: `/whoami-gen ...`

### whoareu

```text
/whoareu prompt 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
/whoareu template otaku
/whoareu reference 贾维斯
```

Or short prompt mode:

```text
/whoareu 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
```
