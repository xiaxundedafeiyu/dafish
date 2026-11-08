# -*- coding: utf-8 -*-
"""配置与凭据。

两个文件都放在 ~/.dafish/ 下（Windows 是 C:\\Users\\<你>\\.dafish\\）：
  config.toml  可提交给世界的偏好：tts 提供方、默认分区、渲染分辨率
  cred.json    **绝不提交**：SESSDATA / bili_jct / DedeUserID

工具只读这两个文件，不代登录、不代扫码、不联网存密码。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


def home() -> Path:
    return Path(os.environ.get("DAFISH_HOME", Path.home() / ".dafish"))


def config_path() -> Path:
    return home() / "config.toml"


def cred_path() -> Path:
    return home() / "cred.json"


@dataclass
class Config:
    default_tid: int = 230
    width: int = 1920
    height: int = 1080
    fps: int = 30
    tts_provider: str = "volc"
    tts_voice: str = "zh_female_tianmeixiaoyuan_uranus_bigtts"
    mascot: str = ""            # 本机角色图路径，**不进仓库**
    ffmpeg: str = "ffmpeg"
    extra: dict = field(default_factory=dict)


DEFAULT_CONFIG_TEXT = """# 大肥鱼自主 · 配置文件
default_tid  = 230        # 默认分区：230 软件应用
width        = 1920
height       = 1080
fps          = 30
tts_provider = "volc"     # volc | none
tts_voice    = "zh_female_tianmeixiaoyuan_uranus_bigtts"
mascot       = ""         # 角色图放本机，别提交
ffmpeg       = "ffmpeg"   # 找不到就写绝对路径
"""


def ensure_home() -> None:
    home().mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    p = config_path()
    cfg = Config()
    if not p.exists() or tomllib is None:
        return cfg
    with p.open("rb") as fh:
        raw = tomllib.load(fh)
    for k, v in raw.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
        else:
            cfg.extra[k] = v
    return cfg


@dataclass
class Cred:
    sessdata: str = ""
    bili_jct: str = ""
    uid: str = ""

    @property
    def complete(self) -> bool:
        return all([self.sessdata, self.bili_jct, self.uid])


def load_cred() -> Cred:
    p = cred_path()
    if not p.exists():
        return Cred()
    try:
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return Cred()
    return Cred(
        sessdata=str(raw.get("sessdata") or raw.get("SESSDATA") or ""),
        bili_jct=str(raw.get("bili_jct") or raw.get("BILI_JCT") or ""),
        uid=str(raw.get("uid") or raw.get("DedeUserID") or ""),
    )
