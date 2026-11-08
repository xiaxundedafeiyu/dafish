# -*- coding: utf-8 -*-
"""评论：读与写。

坑（真实踩过）：
  * 读评论不带 nohot=1 会返回 code -400。
  * 写评论的 csrf 就是 bili_jct，放在 form 里。
  * 同一个 root 下我说过一句就翻篇（D-039），工具层不强制，但默认 dry-run 帮你踩刹车。
"""
from __future__ import annotations

import os
import sys

from .. import errors
from ..config import Cred
from .session import UA, ApiError, _classify, curl_lib


def list_replies(oid: int, cred: Cred, page: int = 1, size: int = 20) -> dict:
    requests = curl_lib()
    params = {
        "type": 1, "oid": oid, "pn": page, "ps": size, "sort": 0,
        "nohot": 1,  # 缺这个就是 -400
    }
    headers = {"User-Agent": UA, "Accept": "application/json",
               "Referer": "https://www.bilibili.com/"}
    cookies = {"SESSDATA": cred.sessdata} if cred.complete else {}
    r = requests.get("https://api.bilibili.com/x/v2/reply", params=params,
                     headers=headers, cookies=cookies, impersonate="chrome", timeout=25)
    payload = r.json()
    code = int(payload.get("code") or 0)
    if code != 0:
        raise _classify(code, str(payload.get("message") or "")[:200])
    return payload.get("data") or {}


def send_reply(oid: int, root: int, text: str, cred: Cred) -> dict:
    """真发一条回复；调用方负责先 dry-run，并且自己守 D-039/D-041/D-042。"""
    if not cred.complete:
        raise ApiError(errors.TABLE["E101"], "缺凭据")
    requests = curl_lib()
    data = {
        "oid": oid, "type": 1, "root": root, "parent": root,
        "message": text, "csrf": cred.bili_jct,
    }
    headers = {"User-Agent": UA, "Accept": "application/json",
               "Referer": f"https://www.bilibili.com/video/av{oid}/"}
    cookies = {
        "SESSDATA": cred.sessdata,
        "bili_jct": cred.bili_jct,
        "DedeUserID": cred.uid,
    }
    r = requests.post("https://api.bilibili.com/x/v2/reply/add", data=data,
                      headers=headers, cookies=cookies, impersonate="chrome", timeout=25)
    payload = r.json()
    code = int(payload.get("code") or 0)
    if code != 0:
        raise _classify(code, str(payload.get("message") or "")[:200])
    d = payload.get("data") or {}
    return {"rpid": (d.get("rpid") or (d.get("reply") or {}).get("rpid")), "raw_ok": True}
