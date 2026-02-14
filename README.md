# WhoWeAre

你的 OpenClaw/Agent 认识你吗？

大多数 AI 助手在第一次对话时，对你一无所知——不知道你写什么代码、玩什么游戏、听什么歌。每次都要从头介绍自己，每次都要重新建立默契。

WhoWeAre 解决的就是这个问题。

只需要丢几个链接，它就能从你的公开主页里提取出一份完整的用户画像（`USER.md`），让 OpenClaw/Agent 在第一句话之前就已经了解你。同样地，你也可以用一句话描述你想要的 Agent 性格，它会生成对应的身份和灵魂文件，让你的 Agent 不再是千篇一律的"我是一个 AI 助手"。

## 效果

- `/myprofile` → 从你的 GitHub、B站、知乎等主页抓取信息，合成一份 Agent 可直接消费的 `USER.md`
- `/whoareu` → 用一句话或一个模板，生成 `IDENTITY.md`（身份）+ `SOUL.md`（性格）。也可以直接指定一个动漫角色、电视剧角色、历史人物等已知角色的名字，系统会自动检索其维基百科信息，生成对应的身份与性格设定

生成的文件会自动写入 OpenClaw workspace，Agent 下次启动时就能读取。已有的同名文件不会被覆盖，而是自动备份。

## 一键部署

```bash
git clone https://github.com/ReinerBRO/WhoWeAre.git
cd WhoWeAre
bash scripts/deploy-openclaw.sh
```

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

| | 平台 | | 平台 |
|:---:|:---|:---:|:---|
| <img src="https://cdn.simpleicons.org/github" width="16"> | GitHub | <img src="https://cdn.simpleicons.org/stackoverflow" width="16"> | Stack Overflow |
| <img src="https://cdn.simpleicons.org/gitlab" width="16"> | GitLab | <img src="https://cdn.simpleicons.org/reddit" width="16"> | Reddit |
| <img src="https://cdn.simpleicons.org/bilibili" width="16"> | Bilibili | <img src="https://cdn.simpleicons.org/steam" width="16"> | Steam |
| <img src="https://cdn.simpleicons.org/zhihu" width="16"> | 知乎 | <img src="https://cdn.simpleicons.org/medium" width="16"> | Medium |
| <img src="https://cdn.simpleicons.org/sinaweibo" width="16"> | 微博 | <img src="https://cdn.simpleicons.org/devdotto" width="16"> | Dev.to |
| <img src="https://cdn.simpleicons.org/douban" width="16"> | 豆瓣 | <img src="https://cdn.simpleicons.org/googlescholar" width="16"> | Google Scholar |
| <img src="https://cdn.simpleicons.org/xiaohongshu" width="16"> | 小红书 | 🌐 | 其他网页 |

### /whoareu — 定义 Agent 的人格

```text
/whoareu 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
/whoareu template otaku
/whoareu reference 贾维斯
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
