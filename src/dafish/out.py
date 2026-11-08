# -*- coding: utf-8 -*-
"""输出契约：stdout 只写 JSON，日志一律走 stderr。

任何子命令都必须通过 ok() / fail() 返回，保证 Agent 能解析。
"""
from __future__ import annotations

import json
import sys
from typing import Any

# 退出码：0 成功 / 2 用法错误 / 3 需要人工介入 / 4 环境缺件
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_HUMAN = 3
EXIT_ENV = 4


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()


def ok(data: Any = None, **extra: Any) -> int:
    payload: dict[str, Any] = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    _emit(payload)
    return EXIT_OK


def fail(error: str, hint: str = "", exit_code: int = EXIT_HUMAN, **extra: Any) -> int:
    """error 用错误分类表里的短码，例如 E601 / E412 / E400 / E101 / ENET。"""
    payload: dict[str, Any] = {"ok": False, "error": error}
    if hint:
        payload["hint"] = hint
    payload.update(extra)
    _emit(payload)
    return exit_code


def log(message: str) -> None:
    """进度信息走 stderr，不污染 stdout 的 JSON。"""
    sys.stderr.write(message.rstrip() + "\n")
    sys.stderr.flush()
