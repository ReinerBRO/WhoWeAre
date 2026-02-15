# WhoWeAre

**[English](README.en.md)** | **日本語** | **[中文](README.md)**

あなたの OpenClaw/Agent は、あなたのことを知っていますか？

ほとんどの AI アシスタントは、初めての会話であなたについて何も知りません——どんなコードを書くのか、どんなゲームをするのか、どんな音楽を聴くのか。毎回自己紹介をやり直し、毎回ゼロから関係を築く必要があります。しかも性格はいつも同じ、「私は AI アシスタントです」。

WhoWeAre はこの問題を解決します。

リンクをいくつか投げるだけで、公開プロフィールから完全なユーザープロファイル（`USER.md`）を抽出し、OpenClaw/Agent が最初のメッセージの前からあなたを理解できるようにします。同様に、一言で Agent の性格を記述したり、キャラクター名を直接指定することもできます——アニメ、ドラマ、歴史上の人物など——システムが自動的にそのキャラクターに基づいたアイデンティティと性格設定を生成します。

## 機能

- `/myprofile` → GitHub、Bilibili、知乎などのプロフィールから情報を取得し、Agent が直接利用できる `USER.md` を合成
- `/whoareu` → プロンプト、テンプレート、またはキャラクター参照から `IDENTITY.md`（アイデンティティ）+ `SOUL.md`（性格）を生成。既知のキャラクターの場合、Wikipedia データを自動取得して正確なペルソナファイルを構築

生成されたファイルは OpenClaw ワークスペースに自動的に書き込まれます。既存の同名ファイルは上書きされず、自動的にバックアップされます。

## クイックスタート

```bash
git clone https://github.com/ReinerBRO/WhoWeAre.git
cd WhoWeAre
bash scripts/deploy-openclaw.sh
```

## 使い方

OpenClaw TUI または OpenClaw に接続された任意のプラットフォーム（Telegram、QQ、WhatsApp など）でコマンドを直接送信します。

### /myprofile — Agent にあなたが誰かを伝える

```text
/myprofile add https://github.com/<you>
/myprofile add https://space.bilibili.com/<id>
/myprofile run
```

一度にまとめて実行することもできます：

```text
/myprofile run https://github.com/<you> https://space.bilibili.com/<id>
```

その他のコマンド：`list`、`clear`、`help`。

`--lang` で出力言語を指定（デフォルト：中国語）：

```text
/myprofile run --lang en    # 英語
/myprofile run --lang ja    # 日本語
/myprofile run --lang zh    # 中国語（デフォルト）
```

対応プラットフォーム：

| | プラットフォーム | リンク形式 |
|:---:|:---|:---|
| <img src="https://cdn.simpleicons.org/github" width="16"> | GitHub | `https://github.com/<user>` |
| <img src="https://cdn.simpleicons.org/gitlab" width="16"> | GitLab | `https://gitlab.com/<user>` |
| <img src="https://cdn.simpleicons.org/bilibili" width="16"> | Bilibili | `https://space.bilibili.com/<uid>` |
| <img src="https://cdn.simpleicons.org/zhihu" width="16"> | 知乎 | `https://zhihu.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/sinaweibo" width="16"> | 微博 (Weibo) | `https://weibo.com/<uid>` |
| <img src="https://cdn.simpleicons.org/douban" width="16"> | 豆瓣 (Douban) | `https://douban.com/people/<id>` |
| <img src="https://cdn.simpleicons.org/googlescholar" width="16"> | Google Scholar | `https://scholar.google.com/citations?user=<id>` |
| <img src="https://cdn.simpleicons.org/xiaohongshu" width="16"> | 小紅書 (Xiaohongshu) | `https://xiaohongshu.com/user/profile/<id>` |
| <img src="https://cdn.simpleicons.org/stackoverflow" width="16"> | Stack Overflow | `https://stackoverflow.com/users/<id>` |
| <img src="https://cdn.simpleicons.org/reddit" width="16"> | Reddit | `https://reddit.com/user/<name>` |
| <img src="https://cdn.simpleicons.org/steam" width="16"> | Steam | `https://steamcommunity.com/id/<name>` |
| <img src="https://cdn.simpleicons.org/medium" width="16"> | Medium | `https://medium.com/@<user>` |
| <img src="https://cdn.simpleicons.org/devdotto" width="16"> | Dev.to | `https://dev.to/<user>` |
| 🌐 | その他のウェブページ | 任意の URL |

### /whoareu — Agent のペルソナを定義する

```text
/whoareu reference ジャービス
/whoareu reference ジャービス --lang en    # 英語出力
/whoareu template otaku
/whoareu template otaku --lang ja          # 日本語出力
/whoareu サイバーゴーストの小夜、毒舌だけど優しい、プライバシー重視
```

## プロジェクト構成

```
llmkit/                      # 共有設定 + ワークスペースパス解決
whoami/                      # リンクスクレイピング & USER.md 合成
whoareu/                     # ペルソナ生成（IDENTITY.md + SOUL.md）
openclaw-whoweare-plugin/    # OpenClaw プラグイン
```

## License

MIT
