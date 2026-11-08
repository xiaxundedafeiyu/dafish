# -*- coding: utf-8 -*-
"""错误分类表。

这张表是本项目最重要的资产：每一条都对应一次真实翻车。
规则只有一句——**写操作永不自动重试**，因为每次重试都会重置服务端的冷却计时。
"""
from __future__ import annotations

from dataclasses import dataclass

from .out import EXIT_ENV, EXIT_HUMAN, EXIT_USAGE


@dataclass(frozen=True)
class Err:
    code: str
    meaning: str
    action: str          # stop / fix / retry_read
    hint: str            # 给人和 Agent 看的一句话
    exit_code: int


# 线上真实遇过的错误；按 code 命中
TABLE: dict[str, Err] = {
    "E601": Err(
        "E601", "上传过快（B 站风控）", "stop",
        "现在什么都不要做。冷却时间无法查询，任何一次请求都会重新计时；"
        "至少等 30 分钟，且不要在等待期间试探接口。",
        EXIT_HUMAN,
    ),
    "E412": Err(
        "E412", "接口风控拦截（HTTP 412 / code -412）", "retry_read",
        "读接口可换 chrome131 UA + 对应 Referer 重试一次；仍失败就停，"
        "不要靠签名或 cookie 反复试，会加深封禁。写接口直接停。",
        EXIT_HUMAN,
    ),
    "E400": Err(
        "E400", "参数不合法", "fix",
        "检查 oid 类型、是否漏了 nohot=1、分页参数是否越界。修完可重试。",
        EXIT_USAGE,
    ),
    "E101": Err(
        "E101", "未登录 / 凭据失效", "stop",
        "请人工重新放置 cookie 到 ~/.dafish/cred.json；工具不代登录、不代扫码。",
        EXIT_HUMAN,
    ),
    "ENET": Err(
        "ENET", "网络异常", "retry_read",
        "读操作可退避重试 2 次；写操作不重试，直接报错让人决定。",
        EXIT_HUMAN,
    ),
    "EENV": Err(
        "EENV", "环境缺件", "fix",
        "先跑 dafish doctor，按提示补 ffmpeg / 凭据 / TTS key。",
        EXIT_ENV,
    ),
}


def from_code(api_code: int) -> Err | None:
    return TABLE.get(f"E{abs(int(api_code))}")


def raise_env(hint: str) -> Err:
    e = TABLE["EENV"]
    return Err(e.code, e.meaning, e.action, hint, e.exit_code)
