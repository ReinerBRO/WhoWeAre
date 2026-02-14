# WhoWeAre

WhoWeAre 是一套给 OpenClaw/AI Agent 用的画像生成工具：

- `whoami`（内部模块）：从公开链接抓取信息并生成 `USER.md`
- `whoareu`：根据你的描述生成人格文件 `SOUL.md` + `IDENTITY.md`
- `llmkit`：共享 LLM 配置层 + OpenClaw workspace 路径解析
- `openclaw-whoweare-plugin`：把上面的能力挂到 OpenClaw 命令里直接调用

> 注意：OpenClaw 已占用 `/whoami` 指令。本项目在聊天中不使用 `/whoami`，统一使用 `/myprofile`。
> `AGENTS.md` 不由 whoareu 生成——它是 Agent 的运维规则，与人格无关，直接使用 OpenClaw 自带的模板即可。

## One-Click Deploy (OpenClaw server)

```bash
curl -fsSL https://raw.githubusercontent.com/ReinerBRO/WhoWeAre/main/scripts/deploy-openclaw.sh | bash
```

可选环境变量（部署前设置）：

- `WHOWEARE_DIR`：安装目录（默认 `$HOME/WhoWeAre`）
- `WHOWEARE_WHOAMI_SYNTHESIS_MODE`：`openclaw`（默认）或 `whoami`
- `WHOWEARE_OPENCLAW_AGENT_ID`：OpenClaw synthesis 使用的 agent（默认 `main`）
- `WHOWEARE_OPENCLAW_FALLBACK_TO_WHOAMI`：`1` 开启回退（默认）/ `0` 关闭
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

```
whoweare/
├── llmkit/                      # 共享 LLM 配置 + workspace 路径解析
├── whoami/                      # 链接抓取与 USER.md 合成
├── whoareu/                     # 人格生成（IDENTITY.md + SOUL.md）
└── openclaw-whoweare-plugin/    # OpenClaw 插件（/myprofile、/whoareu 命令）
```

## Quick Start (CLI)

### 1. Install dependencies

```bash
cd llmkit && python3 -m pip install -e .
cd ../whoami && python3 -m pip install -e .
cd ../whoareu && python3 -m pip install -e .
```

### 2. Run profile CLI (internal `whoami` module)

```bash
python -m whoami.cli \
  --link https://github.com/<you> \
  --link https://space.bilibili.com/<id> \
  --link https://scholar.google.com/citations?user=<id> \
  --output USER.md
```

仅抓取不合成：

```bash
python -m whoami.cli --link https://github.com/<you> --no-llm
```

支持的数据源：GitHub、Bilibili、知乎、Google Scholar、以及通用网页（generic fallback）。

### 3. Run whoareu

```bash
whoareu --prompt "一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私" --install .
```

模板模式：

```bash
whoareu --template otaku --name 小夜 --install .
```

角色参考模式：

```bash
whoareu --reference 贾维斯 --name Friday --install .
```

生成文件：`IDENTITY.md`、`SOUL.md`。

## Use With OpenClaw Plugin

### 1. Install plugin

从 WhoWeAre 仓库根目录：

```bash
openclaw plugins install -l ./openclaw-whoweare-plugin
```

安装后重启 gateway。

### 2. Use commands in OpenClaw

`myprofile` 队列流程：

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile add https://scholar.google.com/citations?user=<id>
/myprofile list
/myprofile run
```

直接运行：

```text
/myprofile run https://github.com/<you> https://www.zhihu.com/people/<id>
```

切换合成模式：

```text
/myprofile run --mode openclaw --agent main
/myprofile run --mode whoami
```

注意：不使用 `/whoami` 指令（避免和 OpenClaw 内置命令冲突）。
兼容别名：`/whoami-gen ...`

默认合成路径：`openclaw` 模式（使用 OpenClaw agent）。
回退路径：`whoami` 模式（直接 litellm 调用）。
输出目标：`<agents.defaults.workspace>/USER.md`，替换前自动备份旧文件。

`whoareu`：

```text
/whoareu prompt 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
/whoareu template otaku
/whoareu reference 贾维斯
/whoareu reference https://zh.moegirl.org.cn/初音未来
```

### 3. Plugin config (optional)

Config key: `plugins.entries.openclaw-whoweare.config`

| 字段 | 说明 |
|------|------|
| `whoamiProjectDir` | whoami 项目路径 |
| `whoareuProjectDir` | whoareu 项目路径 |
| `pythonBin` | Python 可执行文件路径 |
| `whoamiSynthesisMode` | `openclaw`（默认）或 `whoami` |
| `openclawBin` | openclaw CLI 路径 |
| `openclawAgentId` | 合成用的 agent ID |
| `openclawTimeoutMs` | 超时时间 |
| `openclawFallbackToWhoami` | 是否回退到 whoami 模式 |
| `defaultProvider` | 默认 LLM provider |
| `defaultModel` | 默认 LLM model |

## LLM Configuration

`whoami` / `whoareu` 都支持通过参数覆盖模型：

- `--provider`
- `--model`
- `--api-base`
- `--api-key`

也可以通过环境变量读取默认配置（由 `llmkit` 处理）：

- `WWA_PROVIDER`
- `WWA_MODEL`
- `WWA_API_BASE`
- `WWA_API_KEY`

说明：`/myprofile` 在默认 `openclaw` 模式下主要走 OpenClaw agent；`--provider/--model` 参数用于 `whoami` 模式或回退路径。

## License

MIT
