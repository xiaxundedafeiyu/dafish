# -*- coding: utf-8 -*-
"""与 B 站通信的底座：凭据、会话、把服务端错误翻成错误分类表里的码。

铁律（来自两次真实翻车）：
  * 写操作**永不自动重试**——每次请求都会重置服务端冷却计时。
  * 读接口遇 412 只允许换 UA 重试一次。
  * 错误一律走 errors.TABLE，不在调用处散着写 if "601" in msg。
"""
from __future__ import annotations

import os
import sys
import time

from .. import errors
from ..config import Cred

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 本机把 bilibili_api 放在工作区 pylib 里；也可用 DAFISH_PYLIB 指到别处
_PYLIB = os.environ.get("DAFISH_PYLIB") or r"D:\大肥鱼自主\tools\pylib"


def _ensure_pylib() -> None:
    if _PYLIB and os.path.isdir(_PYLIB) and _PYLIB not in sys.path:
        sys.path.insert(0, _PYLIB)


def curl_lib():
    _ensure_pylib()
    from curl_cffi import requests  # noqa: PLC0415
    return requests


def bili_credential(cred: Cred):
    """转成 bilibili_api 的 Credential（投稿要用它）。"""
    _ensure_pylib()
    from bilibili_api.utils.network import Credential  # noqa: PLC0415
    return Credential(
        sessdata=cred.sessdata,
        bili_jct=cred.bili_jct,
        dedeuserid=cred.uid,
        buvid3="",
    )


class ApiError(RuntimeError):
    def __init__(self, err: errors.Err, detail: str = ""):
        super().__init__(f"{err.code} {err.meaning} {detail}".strip())
        self.err = err
        self.detail = detail


def _classify(code: int, detail: str) -> ApiError:
    err = errors.from_code(code) if code else None
    if err is None:
        err = errors.Err(
            f"E{abs(code)}", f"服务端返回 {code}", "stop",
            "未分类错误，先看 detail，不要盲目重试。", errors.EXIT_HUMAN,
        )
    return ApiError(err, detail)


def get_json(url: str, params: dict, *, referer: str = "", write: bool = False,
             cred: Cred | None = None, retry_412_once: bool = True) -> dict:
    """只读接口；遇 412（风控）允许换 UA 重试一次，其余直接抛。"""
    requests = curl_lib()
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if referer:
        headers["Referer"] = referer
    cookies = {}
    if cred and cred.complete:
        cookies = {"SESSDATA": cred.sessdata}

    attempts = 2 if (not write and retry_412_once) else 1
    last: Exception | None = None
    for i in range(attempts):
        try:
            r = requests.get(url, params=params, headers=headers, cookies=cookies,
                             impersonate="chrome", timeout=25)
        except Exception as exc:  # 网络层
            last = exc
            if write:
                raise _classify(0, f"网络异常：{exc}") from exc
            time.sleep(1 + i)
            continue
        if r.status_code == 412:
            last = ApiError(errors.TABLE["E412"], "HTTP 412")
            continue
        try:
            payload = r.json()
        except Exception:
            raise _classify(0, f"非 JSON 响应（很可能是风控页）：HTTP {r.status_code}")
        code = int(payload.get("code", 0) or 0)
        if code != 0:
            raise _classify(code, str(payload.get("message") or payload.get("msg") or "")[:200])
        return payload.get("data") or {}
    if isinstance(last, ApiError):
        raise last
    raise _classify(0, f"网络异常：{last}")
