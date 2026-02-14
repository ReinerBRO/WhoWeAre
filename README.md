# WhoWeAre

OpenClaw 插件，为 AI Agent 生成画像文件。

- `/myprofile`：从公开链接抓取信息，生成 `USER.md`
- `/whoareu`：根据描述生成人格文件 `SOUL.md` + `IDENTITY.md`

## 安装

```bash
openclaw plugins install -l ./openclaw-whoweare-plugin
```

安装后重启 gateway。Python 依赖：

```bash
cd llmkit && pip install -e .
cd ../whoami && pip install -e .
cd ../whoareu && pip install -e .
```

## 使用

在 OpenClaw TUI 或任何接入了 OpenClaw 的聊天平台（Telegram、QQ、WhatsApp 等）中直接发送命令即可。

### /myprofile — 生成 USER.md

添加链接后一键生成：

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile add https://scholar.google.com/citations?user=<id>
/myprofile run
```

也可以直接运行：

```text
/myprofile run https://github.com/<you> https://space.bilibili.com/<id>
```

其他命令：`list`、`clear`、`help`。

支持的数据源：GitHub、Bilibili、知乎、Google Scholar、通用网页。

### /whoareu — 生成 SOUL.md + IDENTITY.md

```text
/whoareu 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
/whoareu template otaku
/whoareu reference 贾维斯
```

## 一键部署（服务器）

```bash
curl -fsSL https://raw.githubusercontent.com/ReinerBRO/WhoWeAre/main/scripts/deploy-openclaw.sh | bash
```

## 项目结构

```
llmkit/                      # 共享配置 + workspace 路径解析
whoami/                      # 链接抓取与 USER.md 合成
whoareu/                     # 人格生成（IDENTITY.md + SOUL.md）
openclaw-whoweare-plugin/    # OpenClaw 插件
```

## License

MIT
