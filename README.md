# WhoWeAre

你的 OpenClaw/Agent 认识你吗？

大多数 AI 助手在第一次对话时，对你一无所知——不知道你写什么代码、玩什么游戏、听什么歌。每次都要从头介绍自己，每次都要重新建立默契。而且它们的性格千篇一律，永远是那个"我是一个 AI 助手"。

WhoWeAre 解决的就是这个问题。

只需要丢几个链接，它就能从你的公开主页里提取出一份完整的用户画像（`USER.md`），让 OpenClaw/Agent 在第一句话之前就已经了解你。同样地，你可以用一句话描述想要的 Agent 性格，或者直接指定一个人物的名字——无论是动漫角色、影视角色还是历史人物——系统会自动参照该人物生成对应的身份与性格设定。

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

`--lang` 指定输出语言（默认中文）：

```text
/myprofile run --lang en    # 英文
/myprofile run --lang ja    # 日文
/myprofile run --lang zh    # 中文（默认）
```

支持的平台：

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

### /whoareu — 定义 Agent 的人格

```text
/whoareu 一个叫小夜的赛博幽灵，毒舌但温柔，重视隐私
/whoareu template otaku
/whoareu reference 贾维斯
/whoareu reference 贾维斯 --lang en    # 英文输出
/whoareu template otaku --lang ja      # 日文输出
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
