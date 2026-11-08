# -*- coding: utf-8 -*-
"""审计日志：append-only，一行一个 JSON。

只记「发生了什么」，**不记密钥**——SESSDATA、bili_jct、api key 一律不落。
用途：事后复盘（为什么这条没发出去）、给别人看（这工具真没乱发）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import home


def log_path() -> Path:
    return home() / "audit.log"


def write(event: str, **fields) -> None:
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "t": datetime.now().astimezone().isoformat(timespec="seconds"),
        "event": event,
    }
    for k, v in fields.items():
        if k.lower() in {"sessdata", "bili_jct", "api_key", "token", "password"}:
            continue
        rec[k] = v
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def tail(n: int = 20) -> list[dict]:
    p = log_path()
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()[-n:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
