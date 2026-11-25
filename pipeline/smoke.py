"""Smoke test: call every provider once, log latency to runs.jsonl, report what works.
  python -m pipeline.smoke
"""
from __future__ import annotations

import shutil
import time

import requests

from pipeline.common import OUTPUTS, check_http, env, load_env, log_run


def gemini_text() -> str:
    model = env("GEMINI_TEXT_MODEL", "gemini-3.8-flash-lite", required=False)
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": env("GEMINI_API_KEY")},
                      json={"contents": [{"parts": [{"text": "Translate to Amharic: 'coffee ceremony'. Reply with the words only."}]}]},
                      timeout=60)
    check_http(r)
    return model, r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def gemini_tts() -> str:
    from pipeline.narration import gemini_tts as tts, pcm_to_wav
    from pipeline.common import load_storyboard
    sb = load_storyboard()
    model = env("GEMINI_TTS_MODEL", sb["models"]["tts"]["model"], required=False)
    pcm, rate = tts(model, sb["models"]["tts"]["voice"], "ሰላም፣ ይህ የሙከራ ድምፅ ነው።")
    out = OUTPUTS / "smoke" / "tts.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    pcm_to_wav(pcm, rate, out)
    return model, str(out)


def cloudflare() -> str:
    from pipeline.keyframes import cf_generate
    from pipeline.common import load_storyboard
    model = load_storyboard()["models"]["keyframes"]["model"]
    img = cf_generate(model, "a black clay jebena coffee pot, gouache illustration", 7, 4)
    out = OUTPUTS / "smoke" / "flux.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    return model, str(out)


def main() -> None:
    load_env()
    checks = [("gemini", "text", gemini_text), ("gemini", "tts", gemini_tts), ("cloudflare", "image", cloudflare)]
    print(f"ffmpeg: {'ok' if shutil.which('ffmpeg') else 'MISSING (install ffmpeg)'}")
    for provider, kind, fn in checks:
        t0 = time.time()
        try:
            model, result = fn()
            dt = time.time() - t0
            log_run("smoke", provider, model, params={"kind": kind}, latency_s=dt, output=result[:200])
            print(f"{provider:10} {kind:6} ok    {dt:5.1f}s  {model}  -> {result[:60]}")
        except SystemExit as e:
            print(f"{provider:10} {kind:6} SKIP  {e}")
        except Exception as e:
            dt = time.time() - t0
            log_run("smoke", provider, kind, latency_s=dt, status="error", error=str(e)[:500])
            print(f"{provider:10} {kind:6} FAIL  {dt:5.1f}s  {str(e)[:150]}")


if __name__ == "__main__":
    main()
