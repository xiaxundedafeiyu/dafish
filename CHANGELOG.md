# 更新日志

## 0.1.0 · 2026-11-08

第一版。四个命令可用，安全层是重点。

### 新增
- `doctor`：检查凭据 / ffmpeg / TTS / 配置，输出 `ready` 与缺件原因
- `stat`：合并两个口径（公开接口实时 + 创作中心 T+1），给出平均播放时长与游客占比
- `comments` / `reply`：读评论树、回一条评论（默认 dry-run）
- `publish`：投稿；默认 dry-run，`--send` 才真发
- `tts`：火山 seed-tts-2.0 合成 mp3
- `render`：`scenes.json` → mp4，支持 card / terminal / lines 三种页型
- `guard`：闸门状态（今日配额、上传间隔、风控锁、已回楼层）

### 安全层
- 遇 601 / 406 落一把 30 分钟锁（`~/.dafish/state.json`），锁存期间任何请求都被拦
- 两次上传最小间隔 30 分钟、每天最多 1 条（均可配置，`--force` 需显式且记审计）
- 同一 root 评论只回一次（幂等）
- `~/.dafish/audit.log` 追加式审计，密钥字段永不落盘

### 已知限制
- 只支持单 P 投稿
- `render` 暂不支持逐字动画与转场
- 角色图需自备，用 `--mascot` 指定，不进仓库
