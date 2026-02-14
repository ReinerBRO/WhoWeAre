# WhoWeAre

WhoWeAre 是一套给 OpenClaw/AI Agent 用的画像生成工具：

- `whoami`：从公开链接抓取信息并生成 `USER.md`
- `whoareu`：根据你的描述生成人格文件 `AGENTS.md` + `SOUL.md` + `IDENTITY.md`
- `openclaw-whoweare-plugin`：把上面两个能力挂到 OpenClaw 命令里直接调用

## Repository Layout

- `llmkit/`：共享 LLM 配置层
- `whoami/`：链接抓取与 `USER.md` 合成
- `whoareu/`：人格生成
- `openclaw-whoweare-plugin/`：OpenClaw 插件（`/whoami`、`/whoareu` 命令）

## Quick Start (CLI)

### 1. Install dependencies

```bash
cd llmkit
python3 -m pip install -e .

cd ../whoami
python3 -m pip install -e .

cd ../whoareu
python3 -m pip install -e .
```

### 2. Run whoami

```bash
cd whoami
whoami \
  --link https://github.com/<you> \
  --link https://space.bilibili.com/<id> \
  --output USER.md
```

Optional:

```bash
whoami --link https://github.com/<you> --no-llm
```

### 3. Run whoareu

```bash
cd ../whoareu
whoareu --prompt "一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私" --install .
```

Or template mode:

```bash
whoareu --template otaku --name 小夜 --install .
```

## Use With OpenClaw Plugin

### 1. Install plugin

From `openclaw` repository root:

```bash
openclaw plugins install -l ./whoweare/openclaw-whoweare-plugin
```

Restart gateway after install.

### 2. Use commands in OpenClaw

`whoami` queue flow:

```text
/whoami add https://github.com/<you>
/whoami add https://space.bilibili.com/<id>
/whoami list
/whoami run
```

Direct run:

```text
/whoami run https://github.com/<you> https://www.zhihu.com/people/<id>
```

`whoareu`:

```text
/whoareu prompt 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
/whoareu template otaku
/whoareu reference 贾维斯
```

### 3. Plugin config (optional)

Config key: `plugins.entries.openclaw-whoweare.config`

Useful fields:

- `whoamiProjectDir`
- `whoareuProjectDir`
- `pythonBin`
- `defaultProvider`
- `defaultModel`

## LLM Configuration

`whoami` / `whoareu` 都支持通过参数覆盖模型：

- `--provider`
- `--model`
- `--api-base`
- `--api-key`

也可以通过环境变量读取默认配置（由 `llmkit` 处理）。

## License

MIT (recommended)

