# -*- coding: utf-8 -*-
"""本地状态：记住「今天发过什么」「哪个 root 已经回过」「风控锁到几点」。

存在的唯一理由：**人是会忘的，Agent 更是**。
B 站的风控按「请求次数」计时，重复投递一次就把冷却重置一次——所以必须落盘。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .config import home

VERSION = 1


def state_path() -> Path:
    return home() / "state.json"


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def load() -> dict:
    p = state_path()
    if not p.exists():
        return {"version": VERSION, "publishes": [], "replies": {}, "locks": {}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"version": VERSION, "publishes": [], "replies": {}, "locks": {}}
    raw.setdefault("publishes", [])
    raw.setdefault("replies", {})
    raw.setdefault("locks", {})
    return raw


def save(st: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def publishes_today(st: dict) -> int:
    today = _now().date().isoformat()
    return sum(1 for p in st["publishes"] if str(p.get("date", "")).startswith(today))


def last_publish(st: dict) -> datetime | None:
    times = [_parse(p.get("at")) for p in st["publishes"]]
    times = [t for t in times if t]
    return max(times) if times else None


def active_lock(st: dict, name: str = "upload") -> datetime | None:
    until = _parse(st.get("locks", {}).get(name))
    if until and until > _now():
        return until
    return None


def record_publish(st: dict, *, bvid: str = "", aid: int | str = "",
                   title: str = "", status: str = "submitted") -> None:
    now = _now()
    st["publishes"].append({
        "date": now.date().isoformat(),
        "at": _iso(now),
        "bvid": bvid,
        "aid": aid,
        "title": title,
        "status": status,
    })
    save(st)


def record_reply(st: dict, root: int | str, rpid: int | str = "", text: str = "") -> None:
    now = _now()
    st["replies"][str(root)] = {"at": _iso(now), "rpid": rpid, "text": text[:120]}
    save(st)


def set_lock(st: dict, minutes: int, name: str = "upload", reason: str = "") -> datetime:
    until = _now() + timedelta(minutes=minutes)
    st.setdefault("locks", {})[name] = _iso(until)
    if reason:
        st["locks"][f"{name}_reason"] = reason
    save(st)
    return until
