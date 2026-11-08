# -*- coding: utf-8 -*-
"""闸门：所有**写操作**必须先过这里。

三条闸（全部来自真实翻车，不是想象）：
  1. 风控锁：上次 601 之后 N 分钟内，一次请求都不许发（每次请求都会重置冷却）。
  2. 最小间隔：两次上传之间至少 30 分钟（默认，可配）。
  3. 今日配额：每天最多 1 条（默认，可配）；超了要 --force 并留下审计。

另外：同一个 root 评论只回一次（D-039）——这是幂等，不是限流。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import state
from .config import Config


class Blocked(RuntimeError):
    def __init__(self, code: str, message: str, *, until: datetime | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.until = until

    def as_dict(self) -> dict:
        d = {"blocked": True, "code": self.code, "reason": self.message}
        if self.until:
            d["until"] = self.until.isoformat(timespec="seconds")
        return d


def check_publish(cfg: Config, *, force: bool = False) -> dict:
    """返回放行信息；不放行就抛 Blocked。"""
    st = state.load()
    now = datetime.now().astimezone()

    lock = state.active_lock(st, "upload")
    if lock:
        raise Blocked(
            "ELOCK",
            f"风控锁未解除（到 {lock.isoformat(timespec='minutes')}）。"
            f"锁存期间**任何请求**都会重置冷却，不要试探。",
            until=lock,
        )

    last = state.last_publish(st)
    gap = timedelta(minutes=int(cfg.min_publish_gap_min or 30))
    if last and now - last < gap:
        raise Blocked(
            "EGAP",
            f"距上次投稿 {(now - last).total_seconds() / 60:.0f} 分钟，"
            f"小于最小间隔 {int(gap.total_seconds() // 60)} 分钟。",
            until=last + gap,
        )

    cap = int(cfg.daily_publish_cap or 1)
    used = state.publishes_today(st)
    if used >= cap and not force:
        raise Blocked(
            "EQUOTA",
            f"今天已发 {used} 条（上限 {cap}）。确需再发请加 --force，"
            f"并在审计里留下理由。",
        )

    return {
        "ok_to_send": True,
        "today_used": used,
        "daily_cap": cap,
        "min_gap_min": int(gap.total_seconds() // 60),
        "forced": bool(used >= cap and force),
    }


def check_reply(root: int | str) -> dict:
    """同一 root 只回一次（D-039）。"""
    st = state.load()
    prev = st["replies"].get(str(root))
    if prev:
        raise Blocked(
            "EREPLIED",
            f"这个楼层已经回过了（{prev.get('at')}，rpid={prev.get('rpid')}）。"
            f"同一 root 只回一条，不再追加。",
        )
    return {"ok_to_send": True, "root": str(root)}


def note_risk_lock(st: dict | None = None, minutes_601: int = 30,
                   minutes_412: int = 30) -> dict:
    """记一把锁；返回给人看的信息。"""
    st = st or state.load()
    until = state.set_lock(st, minutes_601, "upload", reason="遇到 601/412，按 D-016 停手")
    return {"locked_until": until.isoformat(timespec="minutes"),
            "minutes": minutes_601,
            "note": "锁存期间不要发任何请求；到期后也只发一次。"}


def snapshot(cfg: Config) -> dict:
    st = state.load()
    now = datetime.now().astimezone()
    last = state.last_publish(st)
    lock = state.active_lock(st, "upload")
    gap = int(cfg.min_publish_gap_min or 30)
    return {
        "today_publishes": state.publishes_today(st),
        "daily_cap": int(cfg.daily_publish_cap or 1),
        "last_publish": last.isoformat(timespec="seconds") if last else None,
        "minutes_since_last": round((now - last).total_seconds() / 60, 1) if last else None,
        "min_gap_min": gap,
        "upload_lock_until": lock.isoformat(timespec="seconds") if lock else None,
        "replied_roots": len(st["replies"]),
        "state_file": str(state.state_path()),
    }
