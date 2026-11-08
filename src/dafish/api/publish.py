# -*- coding: utf-8 -*-
"""投稿：把一个 mp4 + 封面发出去。

设计约束（全部来自真实翻车）：
  * 封面只能是本地文件路径——传 URL 会被当文件打开，报 Errno 22。
  * 首发只发一次：遇 601/406 直接停，不重试、不 sleep、不"确认一下"。
  * 默认 dry-run；--send 才真发。
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from ..config import Cred


def build_meta(*, tid: int, title: str, desc: str, tags: str, dynamic: str = "") -> dict:
    return {
        "tid": tid,
        "title": title,
        "desc": desc,
        "tags": tags,
        "copyright": 1,
        "no_reprint": 1,
        "original": 1,
        "source": "",
        "desc_format_id": 0,
        "recreate": 0,
        "dynamic": dynamic,
    }


def plan(*, video: str, cover: str, meta: dict) -> dict:
    v, c = Path(video), Path(cover)
    problems = []
    if not v.exists():
        problems.append(f"视频不存在：{v}")
    if not c.exists():
        problems.append(f"封面不存在：{c}")
    if len(meta.get("title", "")) > 80:
        problems.append("标题超过 80 字")
    return {
        "video": str(v),
        "video_mb": round(v.stat().st_size / 1024 / 1024, 2) if v.exists() else None,
        "cover": str(c),
        "meta": meta,
        "problems": problems,
        "will_send": not problems,
    }


async def upload(*, video: str, cover: str, meta: dict, cred: Cred,
                 page_title: str = "", on_chunk=None) -> dict:
    # bilibili_api 通过 session._ensure_pylib 挂进 sys.path
    from .session import _ensure_pylib
    _ensure_pylib()
    from bilibili_api import video_uploader as vu  # noqa: PLC0415
    from .session import bili_credential

    page = vu.VideoUploaderPage(
        path=str(Path(video).resolve()),
        title=(page_title or meta["title"])[:60],
        description="",
    )
    up = vu.VideoUploader(pages=[page], meta=meta,
                          credential=bili_credential(cred),
                          cover=str(Path(cover).resolve()))
    if on_chunk:
        up.add_event_listener(vu.VideoUploaderEvents.AFTER_CHUNK.value, on_chunk)
    res = await up.start()
    data = res or {}
    inner = data.get("data") or {}
    return {
        "aid": inner.get("aid") or data.get("aid"),
        "bvid": inner.get("bvid") or data.get("bvid"),
        "raw": {k: v for k, v in data.items() if k != "data"},
    }
