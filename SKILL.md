# SKILL · dafish

给 Agent 看的手册。人请看 [README](README.md)。

**一句话**：`dafish` 是「渲视频 / 配音 / 读数据 / 投稿 / 回评论」五个动作 + 一套限流安全层。

---

## 1. 什么情况用哪个命令

```
想知道现在能不能干活
  └─ dafish doctor          → ready:true 才能往下

想把自己的稿子数据读出来
  └─ dafish stat --bvid X   → 平均播放时长 ÷ 片长 = 内容问题；播放量 = 分发问题

想做一条视频
  ├─ 先写 scenes.json（card / terminal / lines 三种页型）
  └─ dafish render --scenes scenes.json --out a.mp4

想要配音
  └─ dafish tts --text "..." --out v.mp3

想投稿
  ├─ dafish publish ... --send 的**前面那次**先不加 --send，看 guard 字段
  └─ 确认后加 --send（一天只发一次，见红线 2）

想看/回评论
  ├─ dafish comments --oid <aid>
  └─ dafish reply --oid <aid> --root <rpid> --text "..." --send
```

---

## 2. 红线（违反会伤账号，不是风格问题）

1. **601 之后不许重试**。冷却时间无法查询，任何一次请求都会重新计时。
   工具会自动 `--force` 也绕不过的锁（`ELOCK`），**不要试图绕过**。
2. **同一稿件不许重复 publish**。先 dry-run 拿 `will_send: true` 再发一次；发完 `state.json` 会记住。
3. **不许代登录**。没有 cookie 就去要，不要尝试扫码/密码流程。
4. **写操作失败只报告，不自动重试**。`publish` / `reply` 都是这样设计的。
5. **同一 root 评论只回一次**（`EREPLIED`）。对方没新话就不动。

---

## 3. 失败处置表

| code | 含义 | 该做什么 | 禁止 |
|---|---|---|---|
| `ELOCK` | 风控锁未解除 | 等到 `until` 之后 | 试探接口、`--force` |
| `EQUOTA` | 今日配额用尽（默认 1 条） | 明天再发；确需发加 `--force` 并说明理由 | 反复试 |
| `EGAP` | 距上次投稿不足 30 分钟 | 等 | 缩短间隔 |
| `EREPLIED` | 该楼层已回过 | 不追加 | 换文案重发 |
| `E601` | 上传过快 | 停 ≥30 分钟 | 重试 |
| `E412` | 接口风控 | 读接口重试 1 次；写接口停 | 反复请求 |
| `E400` | 参数不合法 | 按 hint 修 | 猜参数重试 |
| `E101` | 未登录 | 要凭据 | 代登录 |
| `EENV` | 环境缺件 | 跑 doctor | 装一堆不确定的东西 |
| `ENET` | 网络异常 | 读重试 2 次；写停 | 写操作重试 |
| `EPUB` | 投稿未知失败 | 把 detail 原样报给人 | 含糊掩过 |

退出码：`0` 成功 / `2` 用法错 / `3` 需人工介入 / `4` 环境缺件。
**看到 3 或 4 就停下问人，不要自作主张**。

---

## 4. scenes.json 怎么写

```json
{"width": 1920, "height": 1080, "fps": 30, "scenes": [
  {"type": "terminal", "dur": 5, "title": "publish.log",
   "lines": ["$ dafish publish", "", "!失败：406", "+停手 30 分钟"],
   "caption": "底部黑条字幕"},
  {"type": "card", "dur": 5, "title": "标题",
   "options": ["① 选项一", "② 选项二"], "caption": "…"},
  {"type": "lines", "dur": 4, "kicker": "小标",
   "lines": ["正文一行", "正文二行"], "caption": "…"}
]}
```

- `dur` 单位秒；总时长 = 各页 `dur` 之和
- `terminal` 的行首 `!` 红 / `+` 绿 / `$` 灰
- `caption` 是底部 150px 黑条上的字幕
- `--mascot <本机图片>` 会在每页右下角贴角色（可选，不进仓库）
- 已排版好、可当模板的：`examples/scenes.demo.json`、`examples/scenes.60s.json`

---

## 5. 状态与审计在哪

| 文件 | 作用 |
|---|---|
| `~/.dafish/cred.json` | 凭据（**不要提交**） |
| `~/.dafish/config.toml` | 偏好：默认分区、分辨率、TTS 音色、限流参数 |
| `~/.dafish/state.json` | 今天发过什么、回过哪些楼层、锁到几点 |
| `~/.dafish/audit.log` | 追加式审计，一行一个 JSON，**密钥字段不会落盘** |

需要判断「现在能不能发」时，读 `dafish guard` 的 JSON，不要自己推算时间。

---

## 6. 一次完整发布的最小流程

```bash
dafish doctor                                    # ready: true
dafish render --scenes scenes.json --out v.mp4
dafish tts --text "…" --out voice.mp3
dafish publish --video v.mp4 --cover c.png --title "…" --desc-file d.txt --tags "…"
#   ↑ 看 guard.ok_to_send 与 will_send，确认后再：
dafish publish --video v.mp4 --cover c.png --title "…" --desc-file d.txt --tags "…" --send
dafish stat --bvid <拿到的 BV 号>                # 24 小时后再看一次
```
