# -*- coding: utf-8 -*-
"""命令行入口。

子命令一律走 out.ok / out.fail 返回 JSON；--help 才是给人看的文本。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from . import __version__, doctor, out
from . import state as state_mod
from .config import load_config, load_cred


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dafish",
        description="大肥鱼自主 · 让 AI 自己把视频做完并投出去",
    )
    p.add_argument("--version", action="version", version=f"dafish {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("doctor", help="检查环境与凭据，回答「现在能不能投稿」")

    tts = sub.add_parser("tts", help="文字转语音，输出 wav")
    tts.add_argument("--text", required=True)
    tts.add_argument("--out", required=True)
    tts.add_argument("--voice", default="")

    ren = sub.add_parser("render", help="按 scenes.json 渲染成片")
    ren.add_argument("--scenes", required=True)
    ren.add_argument("--out", required=True)
    ren.add_argument("--mascot", default="", help="本机角色图，可选，不进仓库")
    ren.add_argument("--audio", default="", help="可选配音文件，会混进成片")

    pub = sub.add_parser("publish", help="投稿（默认 dry-run，需 --send 才真发）")
    pub.add_argument("--video", required=True)
    pub.add_argument("--cover", required=True)
    pub.add_argument("--title", required=True)
    pub.add_argument("--desc", default="")
    pub.add_argument("--desc-file", default="")
    pub.add_argument("--tags", default="")
    pub.add_argument("--tid", type=int, default=0)
    pub.add_argument("--page-title", default="")
    pub.add_argument("--send", action="store_true", help="真的发出去；不加只打印计划")
    pub.add_argument("--force", action="store_true", help="无视每日配额（会记审计）")

    st = sub.add_parser("stat", help="读一条稿件的播放/时长/粉丝来源")
    st.add_argument("--bvid", required=True)

    rp = sub.add_parser("reply", help="回复某条评论（默认 dry-run，需 --send）")
    rp.add_argument("--oid", required=True, help="稿件 aid")
    rp.add_argument("--root", required=True, help="根评论 rpid")
    rp.add_argument("--text", required=True)
    rp.add_argument("--send", action="store_true")

    sub.add_parser("guard", help="看闸门状态：今天发过没、锁到几点、回过几楼")
    ls = sub.add_parser("comments", help="读一页评论（只读）")
    ls.add_argument("--oid", required=True)
    ls.add_argument("--page", type=int, default=1)
    ls.add_argument("--size", type=int, default=20, help="每页条数；接口上限 20，超出自动夹住")

    return p


def _cmd_publish(args) -> int:
    from pathlib import Path

    from . import audit, errors, guard
    from .api import publish as pub

    cfg = load_config()
    cred = load_cred()
    desc = args.desc
    if args.desc_file:
        desc = Path(args.desc_file).read_text(encoding="utf-8")
    meta = pub.build_meta(
        tid=args.tid or cfg.default_tid,
        title=args.title, desc=desc, tags=args.tags,
    )
    p = pub.plan(video=args.video, cover=args.cover, meta=meta)

    if not args.send:
        try:
            gate = guard.check_publish(cfg, force=args.force)
        except guard.Blocked as blk:
            gate = {"blocked": True, **blk.as_dict(),
                    "note": "dry-run 也会告诉你会不会被拦；这是刻意设计的"}
        return out.ok({"mode": "dry-run", **p, "guard": gate,
                       "next": "确认无误后加 --send 真发（同一条稿件不要重复发）"})
    if p["problems"]:
        audit.write("publish.rejected", reason="plan_problems", problems=p["problems"])
        return out.fail("E400", "；".join(p["problems"]), exit_code=out.EXIT_USAGE)
    if not cred.complete:
        e = errors.TABLE["E101"]
        audit.write("publish.rejected", reason="no_cred")
        return out.fail(e.code, e.hint, exit_code=e.exit_code)

    try:
        gate = guard.check_publish(cfg, force=args.force)
    except guard.Blocked as blk:
        audit.write("publish.blocked", code=blk.code, reason=blk.message)
        return out.fail(blk.code, blk.message, exit_code=out.EXIT_HUMAN,
                        guard=blk.as_dict())

    audit.write("publish.start", video=p["video"], video_mb=p["video_mb"],
                title=meta["title"], tid=meta["tid"], gate=gate)
    try:
        res = asyncio.run(pub.upload(
            video=args.video, cover=args.cover, meta=meta, cred=cred,
            page_title=args.page_title,
            on_chunk=lambda d: out.log("  chunk: " + json.dumps(d, default=str)[:100]),
        ))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "601" in msg:
            e = errors.TABLE["E601"]
            lock = guard.note_risk_lock()
            audit.write("publish.risk", code=601, msg=msg[:200], lock=lock)
            return out.fail(e.code, e.hint, exit_code=e.exit_code, detail=msg[:300], lock=lock)
        if "406" in msg:
            e = errors.TABLE["E412"]
            lock = guard.note_risk_lock()
            audit.write("publish.risk", code=406, msg=msg[:200], lock=lock)
            return out.fail(e.code, e.hint, exit_code=e.exit_code, detail=msg[:300], lock=lock)
        if "-101" in msg or "未登录" in msg:
            e = errors.TABLE["E101"]
            audit.write("publish.fail", code="E101", msg=msg[:200])
            return out.fail(e.code, e.hint, exit_code=e.exit_code, detail=msg[:300])
        audit.write("publish.fail", code="EPUB", msg=msg[:200])
        return out.fail("EPUB", msg[:300], exit_code=out.EXIT_HUMAN)

    st = state_mod.load()
    state_mod.record_publish(st, bvid=str(res.get("bvid") or ""),
                               aid=res.get("aid") or "", title=meta["title"])
    audit.write("publish.done", bvid=res.get("bvid"), aid=res.get("aid"))
    return out.ok(res)


def _cmd_stat(args) -> int:
    from .api import data as api_data
    from .api.session import ApiError

    cred = load_cred()
    try:
        return out.ok(api_data.summarize(args.bvid, cred))
    except ApiError as exc:
        return out.fail(exc.err.code, exc.err.hint, exit_code=exc.err.exit_code,
                        detail=exc.detail)


def _cmd_comments(args) -> int:
    from .api import reply as api_reply
    from .api.session import ApiError

    cred = load_cred()
    try:
        d = api_reply.list_replies(int(args.oid), cred, page=args.page, size=getattr(args, "size", 20))
    except ApiError as exc:
        return out.fail(exc.err.code, exc.err.hint, exit_code=exc.err.exit_code,
                        detail=exc.detail)
    page = d.get("page") or {}
    replies = []
    for r in (d.get("replies") or []):
        replies.append({
            "rpid": r.get("rpid"),
            "user": (r.get("member") or {}).get("uname"),
            "text": (r.get("content") or {}).get("message"),
            "like": r.get("like"),
            "sub_count": r.get("rcount"),
            "sub": [
                {"rpid": s.get("rpid"),
                 "user": (s.get("member") or {}).get("uname"),
                 "text": (s.get("content") or {}).get("message")}
                for s in ((r.get("replies") or [])[:20])
            ],
        })
    return out.ok({"page": int(getattr(args, "page", 1)),
                   "count": page.get("count"),
                   "page_size": page.get("size"),
                   "replies": replies})


def _cmd_reply(args) -> int:
    from . import audit, errors, guard, state as state_mod
    from .api import reply as api_reply
    from .api.session import ApiError

    cred = load_cred()
    if not args.send:
        try:
            gate = guard.check_reply(args.root)
        except guard.Blocked as blk:
            gate = blk.as_dict()
        return out.ok({"mode": "dry-run", "oid": int(args.oid), "root": int(args.root),
                       "text": args.text, "guard": gate,
                       "next": "加 --send 才真发；发过就不要重复发（同 root 只回一次）"})
    if not cred.complete:
        e = errors.TABLE["E101"]
        return out.fail(e.code, e.hint, exit_code=e.exit_code)
    try:
        guard.check_reply(args.root)
    except guard.Blocked as blk:
        audit.write("reply.blocked", root=args.root, code=blk.code)
        return out.fail(blk.code, blk.message, exit_code=out.EXIT_HUMAN,
                        guard=blk.as_dict())
    try:
        res = api_reply.send_reply(int(args.oid), int(args.root), args.text, cred)
    except ApiError as exc:
        audit.write("reply.fail", root=args.root, code=exc.err.code)
        return out.fail(exc.err.code, exc.err.hint, exit_code=exc.err.exit_code,
                        detail=exc.detail)
    st = state_mod.load()
    state_mod.record_reply(st, args.root, res.get("rpid") or "", args.text)
    audit.write("reply.done", root=args.root, rpid=res.get("rpid"))
    return out.ok(res)


def _cmd_guard(args) -> int:
    from . import audit, guard

    cfg = load_config()
    data = guard.snapshot(cfg)
    data["recent_audit"] = audit.tail(5)
    return out.ok(data)


def _cmd_tts(args) -> int:
    from .api.session import ApiError
    from .tts import volc

    cfg = load_config()
    voice = args.voice or cfg.tts_voice
    try:
        audio = volc.synth(args.text, voice=voice)
    except ApiError as exc:
        return out.fail(exc.err.code, exc.err.hint, exit_code=exc.err.exit_code,
                        detail=exc.detail)
    from pathlib import Path
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(audio)
    return out.ok({"out": str(p.resolve()), "kb": round(len(audio) / 1024, 1),
                   "voice": voice, "chars": len(args.text)})


def _cmd_render(args) -> int:
    from .api.session import ApiError
    from .render import core as rc

    cfg = load_config()
    try:
        spec = rc.load_spec(args.scenes)
        res = rc.render(spec, args.out, mascot=args.mascot or cfg.mascot,
                        ffmpeg=cfg.ffmpeg, audio=args.audio)
    except ApiError as exc:
        return out.fail(exc.err.code, exc.err.hint, exit_code=exc.err.exit_code,
                        detail=exc.detail)
    except FileNotFoundError as exc:
        return out.fail("E400", f"文件不存在：{exc}", exit_code=out.EXIT_USAGE)
    return out.ok(res)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.cmd:
        parser.print_help(sys.stderr)
        return out.EXIT_USAGE

    handlers = {
        "doctor": lambda a: doctor.run(),
        "publish": _cmd_publish,
        "stat": _cmd_stat,
        "comments": _cmd_comments,
        "reply": _cmd_reply,
        "tts": _cmd_tts,
        "guard": _cmd_guard,
        "render": _cmd_render,
    }
    if args.cmd in handlers:
        return handlers[args.cmd](args)

    return out.fail("ENOTIMPL", f"子命令 {args.cmd} 尚未实现", exit_code=out.EXIT_USAGE)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
