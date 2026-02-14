# WhoWeAre

WhoWeAre 是一套给 OpenClaw/AI Agent 用的画像生成工具：

- `whoami`：从公开链接抓取信息并生成 `USER.md`
- `whoareu`：根据你的描述生成人格文件 `AGENTS.md` + `SOUL.md` + `IDENTITY.md`
- `openclaw-whoweare-plugin`：把上面两个能力挂到 OpenClaw 命令里直接调用

## One-Click Deploy (OpenClaw server)

```bash
curl -fsSL https://raw.githubusercontent.com/ReinerBRO/WhoWeAre/main/scripts/deploy-openclaw.sh | bash
```

可选环境变量（部署前设置）：

- `WHOWEARE_DIR`：安装目录（默认 `$HOME/WhoWeAre`）
- `WHOWEARE_DEFAULT_PROVIDER`：默认 provider
- `WHOWEARE_DEFAULT_MODEL`：默认 model
- `WHOWEARE_DEFAULT_API_BASE`：默认 API Base
- `WHOWEARE_DEFAULT_API_KEY`：默认 API Key
- `WHOWEARE_NO_RESTART=1`：安装后不自动重启 gateway

示例：

```bash
WHOWEARE_DEFAULT_PROVIDER=openai \
WHOWEARE_DEFAULT_MODEL=gpt-4o \
curl -fsSL https://raw.githubusercontent.com/ReinerBRO/WhoWeAre/main/scripts/deploy-openclaw.sh | bash
```

## Repository Layout

- `llmkit/`：共享 LLM 配置层
- `whoami/`：链接抓取与 `USER.md` 合成
- `whoareu/`：人格生成
- `openclaw-whoweare-plugin/`：OpenClaw 插件（`/myprofile`、`/whoareu` 命令）

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

From `WhoWeAre` repository root:

```bash
openclaw plugins install -l ./openclaw-whoweare-plugin
```

Restart gateway after install.

If you vendor this repo under another workspace (for example under `openclaw/whoweare`), use that path instead.

### 2. Use commands in OpenClaw

`myprofile` queue flow:

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile list
/myprofile run
```

Alias: `/whoami-gen ...`

Direct run:

```text
/myprofile run https://github.com/<you> https://www.zhihu.com/people/<id>
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
