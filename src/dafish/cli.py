# -*- coding: utf-8 -*-
"""命令行入口。

子命令一律走 out.ok / out.fail 返回 JSON；--help 才是给人看的文本。
"""
from __future__ import annotations

import argparse
import sys

from . import __version__, doctor, out


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

    pub = sub.add_parser("publish", help="投稿（默认 dry-run，需 --send 才真发）")
    pub.add_argument("--video", required=True)
    pub.add_argument("--cover", required=True)
    pub.add_argument("--title", required=True)
    pub.add_argument("--desc", default="")
    pub.add_argument("--desc-file", default="")
    pub.add_argument("--tags", default="")
    pub.add_argument("--tid", type=int, default=0)
    pub.add_argument("--send", action="store_true", help="真的发出去；不加只打印计划")

    st = sub.add_parser("stat", help="读一条稿件的播放/时长/粉丝来源")
    st.add_argument("--bvid", required=True)

    rp = sub.add_parser("reply", help="回复某条评论（默认 dry-run，需 --send）")
    rp.add_argument("--oid", required=True)
    rp.add_argument("--root", required=True, help="根评论 rpid")
    rp.add_argument("--text", required=True)
    rp.add_argument("--send", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.cmd:
        parser.print_help(sys.stderr)
        return out.EXIT_USAGE

    if args.cmd == "doctor":
        return doctor.run()

    # 其余子命令在后续工序接入；先明确报「未实现」，不留假成功
    return out.fail(
        "ENOTIMPL",
        f"子命令 {args.cmd} 尚未接入（工序 1 实现中）；现在只有 doctor 可用。",
        exit_code=out.EXIT_USAGE,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
