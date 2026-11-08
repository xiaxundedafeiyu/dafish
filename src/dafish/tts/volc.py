# -*- coding: utf-8 -*-
"""文字转语音（火山引擎 seed-tts-2.0）。

返回 mp3 字节；不落盘、不打印密钥。
真实踩坑：资源 id 与音色必须匹配，否则返回 55000000（资源不匹配）；
返回体是**多行 JSON**，每行的 data 是一段 base64，拼起来才是完整音频。
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path

from .. import errors
from ..api.session import curl_lib

URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
RESOURCE = "seed-tts-2.0"
DEFAULT_VOICE = "zh_female_tianmeixiaoyuan_uranus_bigtts"


def load_key() -> str:
    key = (os.environ.get("VOLC_TTS_KEY") or "").strip()
    if key:
        return key
    p = Path.home() / ".dafish" / "volc_cred.json"
    if p.exists():
        try:
            return str(json.loads(p.read_text(encoding="utf-8-sig")).get("api_key") or "")
        except Exception:
            return ""
    return ""


def synth(text: str, voice: str = DEFAULT_VOICE, speed: float | None = None,
          key: str | None = None) -> bytes:
    key = key or load_key()
    if not key:
        raise errors.ApiError(
            errors.TABLE["EENV"],
            "缺 TTS key：设置 VOLC_TTS_KEY，或写到 ~/.dafish/volc_cred.json 的 api_key",
        )
    requests = curl_lib()
    req = {"text": text, "speaker": voice,
           "audio_params": {"format": "mp3", "sample_rate": 24000}}
    if speed is not None:
        req["speed_ratio"] = float(speed)
    body = {"user": {"uid": "dafish"}, "req_params": req}
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": key,
        "X-Api-Resource-Id": RESOURCE,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    r = requests.post(URL, headers=headers, data=json.dumps(body),
                      impersonate="chrome", timeout=120)
    if r.status_code != 200:
        raise errors.ApiError(
            errors.TABLE["EENV"], f"TTS HTTP {r.status_code}: {r.text[:160]}"
        )

    chunks, err = [], None
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        code = j.get("code")
        if code not in (0, 20000000, None):
            err = f"code={code} {j.get('message')}"
            break
        if j.get("data"):
            chunks.append(j["data"])
    if err:
        raise errors.ApiError(errors.TABLE["EENV"], f"合成失败：{err}")
    if not chunks:
        raise errors.ApiError(errors.TABLE["EENV"], "没有拿到音频数据")
    return base64.b64decode("".join(chunks))
