# -*- coding: utf-8 -*-
"""把 scenes.json 渲成 mp4。

设计目标：**数据驱动**——页面不写死在代码里，陌生 Agent 给一份 JSON 就能出片。
第一版支持三种页型：
  card     大字标题 + 可选多行选项（做投票/结论页）
  terminal 深色终端窗口 + 若干行（做证据/日志页）
  lines     小标 + 若干行正文（做说明页）

共用元素：底部黑条字幕（caption）、右下角角色（--mascot，可选，不进仓库）。
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import errors

BG = (20, 22, 26)
FG = (248, 246, 240)
ACC = (214, 168, 92)
DIM = (150, 155, 164)
BAR_H = 150

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
_BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise errors.ApiError(errors.TABLE["EENV"], "找不到中文字体（msyh.ttc / NotoSansCJK）")


def _fit(draw: ImageDraw.ImageDraw, text: str, font_paths: list[str],
         size: int, max_w: int, min_size: int = 28) -> ImageFont.FreeTypeFont:
    f = _font(font_paths, size)
    while draw.textlength(text, font=f) > max_w and f.size > min_size:
        f = _font(font_paths, f.size - 4)
    return f


def _draw_caption(img: Image.Image, caption: str) -> None:
    if not caption:
        return
    w, h = img.size
    d = ImageDraw.Draw(img)
    d.rectangle([0, h - BAR_H, w, h], fill=(10, 11, 13))
    f = _fit(d, caption, _BOLD_CANDIDATES, 58, w - 160)
    d.text((80, h - BAR_H + (BAR_H - f.size) // 2 - 8), caption, font=f, fill=FG)


def _paste_mascot(img: Image.Image, mascot: str, height: int = 620) -> None:
    if not mascot or not os.path.exists(mascot):
        return
    ch = Image.open(mascot).convert("RGBA")
    scale = height / ch.height
    ch = ch.resize((int(ch.width * scale), height), Image.LANCZOS)
    w, h = img.size
    img.paste(ch, (w - ch.width - 70, h - BAR_H - height + 40), ch)


def _frame_card(w: int, h: int, sc: dict) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    area_h = h - BAR_H
    title = str(sc.get("title", ""))
    f1 = _fit(d, title, _BOLD_CANDIDATES, 96, w - 760)
    d.text((160, 240), title, font=f1, fill=FG)
    d.rectangle([164, 240 + f1.size + 26, 164 + 260, 240 + f1.size + 34], fill=ACC)

    y = 240 + f1.size + 90
    for line in (sc.get("options") or []):
        f = _fit(d, line, _FONT_CANDIDATES, 52, w - 760)
        d.text((160, y), line, font=f, fill=(196, 200, 208))
        y += int(f.size * 1.75)

    sub = sc.get("sub")
    if sub:
        f = _fit(d, sub, _FONT_CANDIDATES, 46, w - 760)
        d.text((160, y + 20), sub, font=f, fill=DIM)

    _draw_caption(img, sc.get("caption", ""))
    return img


def _frame_terminal(w: int, h: int, sc: dict) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    pad = 60
    x0, y0 = 200, 150
    x1, y1 = w - 380, h - BAR_H - 60
    d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=(16, 18, 22), outline=(52, 56, 64), width=2)
    d.rounded_rectangle([x0, y0, x1, y0 + 52], radius=14, fill=(28, 31, 37))
    d.rectangle([x0, y0 + 36, x1, y0 + 52], fill=(28, 31, 37))
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        d.ellipse([x0 + 22 + i * 30, y0 + 18, x0 + 40 + i * 30, y0 + 36], fill=c)
    f_title = _font(_FONT_CANDIDATES, 26)
    d.text((x0 + 130, y0 + 14), str(sc.get("title", "")), font=f_title, fill=(150, 155, 164))

    y = y0 + 100
    for line in (sc.get("lines") or []):
        raw = str(line)
        color = FG
        if raw.startswith("!"):
            color, raw = (240, 130, 120), raw[1:]
        elif raw.startswith("+"):
            color, raw = (140, 210, 150), raw[1:]
        elif raw.startswith("$"):
            color = (160, 170, 185)
        f = _fit(d, raw, _FONT_CANDIDATES, int(sc.get("font_size", 34)), x1 - x0 - 80)
        d.text((x0 + 40, y), raw, font=f, fill=color)
        y += int(f.size * 1.55)
        if y > y1 - 40:
            break
    _draw_caption(img, sc.get("caption", ""))
    return img


def _frame_lines(w: int, h: int, sc: dict) -> Image.Image:
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    kicker = str(sc.get("kicker", ""))
    if kicker:
        fk = _fit(d, kicker, _FONT_CANDIDATES, 44, 900)
        d.text((160, 180), kicker, font=fk, fill=ACC)
        d.rectangle([164, 180 + fk.size + 18, 164 + 120, 180 + fk.size + 24], fill=ACC)
    y = 300
    for line in (sc.get("lines") or []):
        f = _fit(d, line, _FONT_CANDIDATES, 56, w - 400)
        d.text((160, y), line, font=f, fill=FG)
        y += int(f.size * 1.7)
    _draw_caption(img, sc.get("caption", ""))
    return img


_RENDERERS = {"card": _frame_card, "terminal": _frame_terminal, "lines": _frame_lines}


def _storyboard(spec: dict, mascot: str) -> list[tuple[Image.Image, float]]:
    w = int(spec.get("width", 1920))
    h = int(spec.get("height", 1080))
    frames: list[tuple[Image.Image, float]] = []
    for sc in spec.get("scenes", []):
        kind = sc.get("type", "card")
        fn = _RENDERERS.get(kind)
        if fn is None:
            raise errors.ApiError(
                errors.TABLE["E400"],
                f"未知页型 {kind}；支持 {sorted(_RENDERERS)}",
            )
        img = fn(w, h, sc)
        _paste_mascot(img, sc.get("mascot") or mascot)
        frames.append((img, float(sc.get("dur", 6))))
    if not frames:
        raise errors.ApiError(errors.TABLE["E400"], "scenes 为空")
    return frames


def render(spec: dict, out_path: str, *, mascot: str = "",
           ffmpeg: str = "ffmpeg", audio: str = "") -> dict:
    fps = int(spec.get("fps", 30))
    widths = {sc.get("width") for sc in spec.get("scenes", []) if sc.get("width")}
    w = int(spec.get("width", widths.pop() if widths else 1920))
    h = int(spec.get("height", 1080))
    board = _storyboard({**spec, "width": w, "height": h}, mascot)

    total = sum(d for _, d in board)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "pipe:0"]
    if audio:
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    try:
        for img, dur in board:
            raw = img.convert("RGB").tobytes()
            for _ in range(max(1, int(dur * fps))):
                proc.stdin.write(raw)  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]
    except BrokenPipeError as exc:  # ffmpeg 提前退出
        raise errors.ApiError(errors.TABLE["EENV"], f"ffmpeg 断了：{exc}") from exc

    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise errors.ApiError(errors.TABLE["EENV"], f"ffmpeg 退出 {code}: {err[:300]}")

    size_mb = round(os.path.getsize(out_path) / 1024 / 1024, 2)
    return {"out": str(Path(out_path).resolve()), "width": w, "height": h,
            "fps": fps, "seconds": round(total, 2), "mb": size_mb,
            "scenes": len(board), "audio": bool(audio)}


def load_spec(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
