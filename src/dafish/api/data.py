# -*- coding: utf-8 -*-
"""读一条稿件的真实数据。

两个口径（都记住，别混）：
  * 公开接口 x/web-interface/view    —— 播放/点赞/评论，实时
  * 创作中心 x/web/data/archive      —— 平均播放时长、粉丝/游客占比，T+1

没有"总时长 51 秒 / 平均播放 8 秒"这一对的账号，看不出内容问题。
"""
from __future__ import annotations

from ..config import Cred
from .session import ApiError, get_json


def resolve_aid(bvid: str, cred: Cred) -> int:
    data = get_json(
        "https://api.bilibili.com/x/web-interface/view",
        {"bvid": bvid},
        referer=f"https://www.bilibili.com/video/{bvid}/",
        cred=cred,
    )
    aid = data.get("aid")
    if not aid:
        raise ApiError(*[__import__("dafish.errors", fromlist=["TABLE"]).TABLE["E400"],
                         "view 返回里没有 aid"])
    return int(aid)


def archive_stats(aid: int, cred: Cred) -> dict:
    """创作中心逐条数据；需要登录态，且必须是自己的稿件。"""
    return get_json(
        "https://member.bilibili.com/x/web/data/archive",
        {"aid": aid},
        referer="https://member.bilibili.com/platform/analysis/data",
        cred=cred,
    )


def summarize(bvid: str, cred: Cred) -> dict:
    view = get_json(
        "https://api.bilibili.com/x/web-interface/view",
        {"bvid": bvid},
        referer=f"https://www.bilibili.com/video/{bvid}/",
        cred=cred,
    )
    aid = int(view.get("aid") or 0)
    stat = view.get("stat") or {}
    out = {
        "bvid": bvid,
        "aid": aid,
        "title": view.get("title"),
        "duration": view.get("duration"),
        "pubdate": view.get("pubdate"),
        "public": {
            "view": stat.get("view"),
            "like": stat.get("like"),
            "reply": stat.get("reply"),
            "coin": stat.get("coin"),
            "favorite": stat.get("favorite"),
            "share": stat.get("share"),
        },
    }
    try:
        d = archive_stats(aid, cred)
    except ApiError as exc:
        out["member"] = {"error": exc.err.code, "hint": exc.err.hint}
        return out

    play = d.get("play") or {}
    group = d.get("group") or {}
    ms = d.get("stat") or {}
    fans = int(group.get("fans") or 0)
    guest = int(group.get("guest") or 0)
    total = fans + guest
    avg = play.get("avg_duration")
    dur = play.get("duration")
    out["member"] = {
        "play": ms.get("play"),
        "like": ms.get("like"),
        "reply": ms.get("reply"),
        "duration": dur,
        "avg_duration": avg,
        "avg_ratio": round(avg / dur, 3) if (avg and dur) else None,
        "fans": fans,
        "guest": guest,
        "guest_ratio": round(guest / total, 4) if total else None,
    }
    return out
