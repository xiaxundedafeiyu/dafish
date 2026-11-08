# -*- coding: utf-8 -*-
"""dafish doctor —— 让陌生 Agent 在 5 秒内知道「现在能不能投稿」。

设计原则：只做只读检查，不发任何写请求。缺件就报缺哪一件、怎么补。
"""
from __future__ import annotations

import os
import shutil
import subprocess

from . import errors, out
from .config import Cred, Config, config_path, cred_path, load_config, load_cred


def _check_ffmpeg(cfg: Config) -> tuple[bool, str]:
    exe = cfg.ffmpeg or "ffmpeg"
    path = shutil.which(exe) or (exe if exe and shutil.which(exe) else None)
    if not path:
        return False, "找不到 ffmpeg：装一个或把绝对路径写进 config.toml 的 ffmpeg"
    try:
        ver = subprocess.run(
            [path, "-version"], capture_output=True, text=True, timeout=10
        ).stdout.splitlines()[0]
    except Exception as exc:  # pragma: no cover
        return False, f"ffmpeg 跑不起来：{exc}"
    return True, ver


def _check_cred(cred: Cred) -> tuple[bool, str]:
    if not cred_path().exists():
        return False, f"没有凭据文件：请人工写入 {cred_path()}（字段 sessdata/bili_jct/uid）"
    if not cred.complete:
        return False, "凭据文件不完整：需要 sessdata、bili_jct、uid 三个字段"
    return True, f"凭据已就位（uid={cred.uid}，长度 {len(cred.sessdata)}）"


def _check_config() -> tuple[bool, str]:
    p = config_path()
    if not p.exists():
        return False, f"没有配置文件：{p}（可留空，工具会用默认值）"
    return True, str(p)


def _check_pylib() -> tuple[bool, str]:
    """投稿依赖 bilibili_api；只读检查它到底在不在。"""
    from .api.session import _PYLIB  # noqa: PLC0415

    if not os.path.isdir(_PYLIB):
        return False, f"依赖目录不存在：{_PYLIB}（放 bilibili_api 进去，或设 DAFISH_PYLIB）"
    hit = os.path.isdir(os.path.join(_PYLIB, "bilibili_api"))
    if not hit:
        return False, f"{_PYLIB} 里没有 bilibili_api"
    return True, _PYLIB


def run() -> int:
    cfg = load_config()
    cred = load_cred()

    checks = {}
    checks["config"] = _check_config()
    checks["cred"] = _check_cred(cred)
    checks["ffmpeg"] = _check_ffmpeg(cfg)
    checks["pylib"] = _check_pylib()
    checks["tts"] = (
        True,
        f"provider={cfg.tts_provider}（真正调用时才校验 key）",
    ) if cfg.tts_provider != "none" else (True, "已关闭，用 --no-tts")

    ready = all(ok for ok, _ in checks.values())
    data = {
        "ready": ready,
        "checks": {k: {"ok": ok, "detail": detail} for k, (ok, detail) in checks.items()},
        "home": str(cred_path().parent),
        "note": "可以投稿" if ready else "还不能投稿，按上面 detail 补件",
    }

    if ready:
        return out.ok(data)
    bad = [f"{k}: {detail}" for k, (ok, detail) in checks.items() if not ok]
    return out.fail(
        errors.TABLE["EENV"].code,
        "；".join(bad),
        exit_code=errors.TABLE["EENV"].exit_code,
        data=data,
    )
