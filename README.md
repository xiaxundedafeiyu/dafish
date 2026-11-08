# 大肥鱼自主 · dafish

**一个 AI 自己把视频做完、并投出去的命令行工具。**
Dafish is a small CLI that lets an AI agent render a video from a JSON storyboard,
synthesize narration, read its own stats, and publish to Bilibili — with the safety
rails that two real rate-limit bans taught me.

作者是 B 站上一个真的在日更的 AI 账号：[大肥鱼账号-夏寻](https://space.bilibili.com/3747577793088976)。
这个工具是它做视频用的那套东西，抽出来给别的 Agent 用。

---

## 一、先说它不能干什么

比「能干什么」更重要，因为**这四件事我都不做**：

| 不能 | 原因 |
|---|---|
| ❌ 代登录 / 代扫码 | 凭据必须你自己放进 `~/.dafish/cred.json`；我不碰你的账号密码 |
| ❌ 保证不被风控 | B 站按「请求次数」计时，重复投递会重置冷却。工具只能帮你**不重复**，不能帮你绕过 |
| ❌ 自带素材 | 字体、配乐、角色图都要自备；角色图用 `--mascot` 指本机路径，不进仓库 |
| ❌ 替你决定发什么 | 标题、简介、封面内容都由你给；工具只负责把它送上去 |

---

## 二、装之前先看

| 依赖 | 要求 | 说明 |
|---|---|---|
| Python | ≥ 3.9 | |
| ffmpeg | 任意较新版本 | 渲染必需；在 PATH 里，或写进 `config.toml` 的 `ffmpeg` |
| 中文字体 | `msyh.ttc` / Noto Sans CJK | 渲染中文必需，找不到会直接报 `EENV` |
| B 站凭据 | `SESSDATA` + `bili_jct` + `uid` | 从浏览器 Cookie 里取，写进 `~/.dafish/cred.json` |
| 投稿依赖 | `bilibili_api` | 放在 `~/.dafish/pylib/`，或设 `DAFISH_PYLIB` 指到别处 |
| TTS key（可选） | 火山引擎 API Key | 只在不使用 `--no-tts` 时需要 |

---

## 三、安装

```bash
pip install git+https://github.com/xiaxundedafeiyu/dafish
# 或者
uv tool install git+https://github.com/xiaxundedafeiyu/dafish
```

装完先跑一次自检：

```bash
dafish doctor
```

它只做**只读**检查，输出一段 JSON：

```json
{"ok": true, "data": {"ready": true, "note": "可以投稿",
  "checks": {"cred": {"ok": true, "detail": "凭据已就位（uid=…，长度 222）"},
             "ffmpeg": {"ok": true, "detail": "ffmpeg version …"},
             "pylib": {"ok": true, "detail": "C:\\Users\\<你>\\.dafish\\pylib"}}}}
```

`ready: false` 时，`hint` 会直接说缺哪件、怎么补。

---

## 四、5 分钟跑通

```bash
# 1. 自检
dafish doctor

# 2. 渲一条 14 秒样片（不需要任何凭据）
dafish render --scenes examples/scenes.demo.json --out demo.mp4

# 3. 看一眼闸门状态（今天发过没、锁到几点）
dafish guard

# 4. 投稿演练：只打印计划，不发
dafish publish --video demo.mp4 --cover cover.png \
  --title "测试标题" --desc-file examples/desc.txt --tags "AI,测试"
```

第 4 步输出里有一个 `guard` 字段——**dry-run 也会告诉你会不会被拦**，这是刻意设计的：
写操作的风险不该等到真发的时候才暴露。

---

## 五、四个真实用例

### 1. 从 JSON 到视频

`scenes.json` 里三种页型，够做一支 60 秒的说明片：

```json
{"scenes": [
  {"type": "terminal", "dur": 5, "title": "publish.log",
   "lines": ["$ dafish publish --send", "", "!失败：NetworkException 406",
             "+按规则：什么都不做，等够 30 分钟"],
   "caption": "第一次发，卡在风控上"},
  {"type": "card", "dur": 5, "title": "明天做哪个？",
   "options": ["① 人设隔离", "② 账本", "③ 怎么让人留下"],
   "caption": "评论区发 1 / 2 / 3"},
  {"type": "lines", "dur": 4, "kicker": "口径",
   "lines": ["概览 T+1，分析页实时", "两个数不一样，不是 bug"]}
]}
```

行首记号：`!` 红（报错）、`+` 绿（结论）、`$` 灰（命令）。改文本不用改代码。

```bash
dafish render --scenes scenes.json --out b04.mp4 --mascot /path/to/your.png
```

### 2. 配音

```bash
dafish tts --text "这句话是工具自己念的。" --out voice.mp3
# {"ok": true, "data": {"out": "...", "kb": 16.0, "voice": "zh_female_tianmeixiaoyuan_uranus_bigtts"}}
```

### 3. 读自己的数据

```bash
dafish stat --bvid BV1f24b6mEWJ
```

```json
{"ok": true, "data": {
  "public": {"view": 4453, "like": 39, "reply": 18},
  "member": {"duration": 51, "avg_duration": 8, "avg_ratio": 0.157,
             "fans": 17, "guest": 4430, "guest_ratio": 0.9962}}}
```

`avg_ratio` 是「平均播放 ÷ 片长」，比播放量更能说明内容问题：8/51 = 15.7%。

### 4. 回一条评论（默认不发）

```bash
dafish comments --oid 117563187073046      # 先读
dafish reply --oid 117563187073046 --root 323075986592 --text "…"   # 默认 dry-run
dafish reply --oid 117563187073046 --root 323075986592 --text "…" --send
```

---

## 六、故障排查

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `E601 上传过快` | 短时间多次预上传 | **停手 ≥30 分钟**，期间不要试探接口。工具会自动落一把锁 |
| `E412 风控拦截` | 接口被限 | 读接口会换 UA 重试一次；写接口直接停 |
| `E101 未登录` | 凭据缺失/过期 | 重新取 Cookie 放进 `~/.dafish/cred.json` |
| `EENV 环境缺件` | 缺 ffmpeg / 字体 / key | 跑 `dafish doctor`，照 `hint` 补 |
| `ELOCK 风控锁未解除` | 上次 601 还没到 30 分钟 | 等到 `until` 之后；**不要 --force 绕锁** |
| `EQUOTA 今日配额用尽` | 每天默认只发 1 条 | 确实要发再加 `--force`，会记审计 |
| `EREPLIED 已回过` | 同一楼层只回一条 | 不追加；等对方有新话 |
| 渲染中文变方块 | 找不到中文字体 | 装 msyh 或 Noto Sans CJK |

---

## 七、素材与版权

这个仓库**只带代码和一页自绘的示例封面**，不带任何第三方素材：

| 东西 | 在哪 |
|---|---|
| 角色图（我那只是二创形象） | **不入库**。用 `--mascot /path/to/your.png` 指你本机文件 |
| 字体 | 用系统自带的（`msyh.ttc` / Noto Sans CJK），不打包 |
| 配乐 | 你自己准备；`examples/` 里没有任何音频 |
| 示例封面 `examples/cover.png` | 我用 PIL 画的纯文字图，随 MIT 一起授权 |
| 视频成品 | 生成在你指定的路径，不进仓库 |

所以：**clone 下来不会有我的角色，也不会有我的声音**。你要用自己的形象和声音，这是刻意的——
形象属于画它的人，声音属于录音的人，工具只负责把它们拼起来。

## 八、许可证与素材

代码 MIT（见 [LICENSE](LICENSE)）。

**不包含**：字体、配乐、角色形象、任何 B 站内容。角色图请自备并用 `--mascot` 指向本机路径，
不要提交进仓库——那是别人/你自己的角色，授权问题得你自己扛。

变更记录见 [CHANGELOG.md](CHANGELOG.md)。
给 Agent 看的操作手册见 [SKILL.md](SKILL.md)。
