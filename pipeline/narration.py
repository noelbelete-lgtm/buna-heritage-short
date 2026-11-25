"""Stage 4: narration. One Amharic line per shot with Gemini TTS, one WAV per shot.

  python -m pipeline.narration
  python -m pipeline.narration --only s07
"""
from __future__ import annotations

import argparse
import base64
import re
import tempfile
import time

import requests

from pipeline.common import (OUTPUTS, Manifest, check_http, env, ffmpeg, load_env, load_storyboard, log_run,
                             probe_duration, rel, select_shots, stable_hash, with_retries)

STAGE = "narration"


def tts_model(sb: dict) -> str:
    # Model ids change; override with GEMINI_TTS_MODEL without editing the storyboard.
    return env("GEMINI_TTS_MODEL", sb["models"]["tts"]["model"], required=False)


def expected_key(sb: dict, shot: dict) -> str:
    t = sb["models"]["tts"]
    return stable_hash({"model": tts_model(sb), "voice": t["voice"], "style": t["style"], "text": shot["narration"]["am"]})


def gemini_tts(model: str, voice: str, text: str) -> tuple[bytes, int]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": env("GEMINI_API_KEY"), "Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    resp = requests.post(url, headers=headers, json=body, timeout=180)
    check_http(resp)
    part = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    rate = int(m.group(1)) if (m := re.search(r"rate=(\d+)", part.get("mimeType", ""))) else 24000
    return base64.b64decode(part["data"]), rate


def pcm_to_wav(pcm: bytes, rate: int, out) -> None:
    """Raw 16-bit PCM -> 48 kHz mono WAV with leading/trailing silence trimmed (so timing is honest)."""
    with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
        tmp.write(pcm)
        tmp.flush()
        trim = "silenceremove=start_periods=1:start_threshold=-50dB"
        ffmpeg("-f", "s16le", "-ar", rate, "-ac", 1, "-i", tmp.name,
               "-af", f"{trim},areverse,{trim},areverse,aresample=48000", "-ac", 1, out)


def run(only=None, force=False) -> None:
    load_env()
    sb = load_storyboard()
    t = sb["models"]["tts"]
    model = tts_model(sb)
    manifest = Manifest(STAGE)
    for shot in select_shots(sb, only):
        key = expected_key(sb, shot)
        if not force and manifest.valid(shot["id"], key):
            print(f"  {shot['id']}: cached")
            continue
        out = OUTPUTS / STAGE / f"{shot['id']}_{key[:10]}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        text = f"{t['style']}\n{shot['narration']['am']}"
        ctx = dict(stage=STAGE, provider=t["provider"], model=model, shot_id=shot["id"],
                   params={"voice": t["voice"], "style": t["style"], "chars": len(shot["narration"]["am"])}, cache_key=key)
        try:
            (pcm, rate), latency, attempt = with_retries(lambda: gemini_tts(model, t["voice"], text), log_ctx=ctx)
            pcm_to_wav(pcm, rate, out)
        except Exception as e:
            print(f"  {shot['id']}: FAILED ({e}). The shot will be silent; see FAILURES.md")
            continue
        dur = probe_duration(out)
        log_run(**ctx, latency_s=latency, output=rel(out), audio_s=round(dur, 2), attempt=attempt)
        manifest.set(shot["id"], key=key, path=rel(out), duration_s=round(dur, 3), text=shot["narration"]["am"])
        words = len(shot["narration"]["am"].split())
        print(f"  {shot['id']}: {dur:.1f}s audio ({words / dur:.2f} words/s) in {latency:.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    run(a.only, a.force)
    print(f"narration stage done in {time.time() - t0:.1f}s")
