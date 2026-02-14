# WhoWeAre

你的 OpenClaw/Agent 认识你吗？

大多数 AI 助手在第一次对话时，对你一无所知——不知道你写什么代码、玩什么游戏、听什么歌。每次都要从头介绍自己，每次都要重新建立默契。

WhoWeAre 解决的就是这个问题。

只需要丢几个链接，它就能从你的公开主页里提取出一份完整的用户画像（`USER.md`），让 OpenClaw/Agent 在第一句话之前就已经了解你。同样地，你也可以用一句话描述你想要的 Agent 性格，它会生成对应的身份和灵魂文件，让你的 Agent 不再是千篇一律的"我是一个 AI 助手"。

## 效果

- `/myprofile` → 从你的 GitHub、B站、知乎等主页抓取信息，合成一份 Agent 可直接消费的 `USER.md`
- `/whoareu` → 用一句话或一个模板，生成 `IDENTITY.md`（身份）+ `SOUL.md`（性格）

生成的文件会自动写入 OpenClaw workspace，Agent 下次启动时就能读取。

## 安装

通过 OpenClaw TUI 配置插件，或手动安装：

```bash
openclaw plugins install -l ./openclaw-whoweare-plugin
```

Python 依赖：

```bash
cd llmkit && pip install -e .
cd ../whoami && pip install -e .
cd ../whoareu && pip install -e .
```

安装后重启 gateway。

## 使用

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

支持的平台：

| 平台 | 链接格式 |
|------|----------|
| GitHub | `github.com/<user>` |
| GitLab | `gitlab.com/<user>` |
| Bilibili | `space.bilibili.com/<uid>` |
| 知乎 | `zhihu.com/people/<id>` |
| 微博 | `weibo.com/<uid>` |
| 豆瓣 | `douban.com/people/<id>` |
| Google Scholar | `scholar.google.com/citations?user=<id>` |
| Stack Overflow | `stackoverflow.com/users/<id>` |
| Reddit | `reddit.com/user/<name>` |
| Steam | `steamcommunity.com/id/<name>` |
| Medium | `medium.com/@<user>` |
| Dev.to | `dev.to/<user>` |
| 其他网页 | 任意 URL（通用抓取） |

### /whoareu — 定义 Agent 的人格

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
