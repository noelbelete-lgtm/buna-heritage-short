"""Stage 2: keyframes. One still per shot from FLUX on Cloudflare Workers AI.

  python -m pipeline.keyframes                 # all shots (cached ones are skipped)
  python -m pipeline.keyframes --only s03 s05  # just these shots
  python -m pipeline.keyframes --sheet         # reference sheets (4 seeds per reference)
  python -m pipeline.keyframes --candidates 4 --only s03   # explore seeds, then copy the best seed into storyboard.json
"""
from __future__ import annotations

import argparse
import base64
import time

import requests

from pipeline.common import (OUTPUTS, Manifest, check_http, env, load_env, load_storyboard, log_run, rel,
                             select_shots, stable_hash, with_retries)

STAGE = "keyframes"


def build_prompt(sb: dict, shot: dict) -> str:
    """Prompt = shot prompt + verbatim reference descriptions + fixed style block.
    Re-using the exact same reference text in every shot is what keeps things consistent."""
    parts = [shot["keyframe"]["prompt"]]
    parts += [sb["references"][r]["description"] for r in shot["refs"]]
    parts.append(sb["style_block"])
    return ". ".join(p.rstrip(". ") for p in parts)


def expected_key(sb: dict, shot: dict) -> str:
    m = sb["models"]["keyframes"]
    return stable_hash({"model": m["model"], "steps": m["steps"], "prompt": build_prompt(sb, shot),
                        "seed": shot["keyframe"]["seed"], "size": 1024})


def cf_generate(model: str, prompt: str, seed: int, steps: int) -> bytes:
    account = env("CLOUDFLARE_ACCOUNT_ID")
    token = env("CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    if model.rsplit("/", 1)[-1].startswith("flux-2"):
        # FLUX.2 models on Workers AI take multipart form data
        fields = {"prompt": prompt, "steps": steps, "seed": seed, "width": 1024, "height": 1024}
        resp = requests.post(url, headers=headers, files={k: (None, str(v)) for k, v in fields.items()}, timeout=180)
    else:
        resp = requests.post(url, headers=headers, json={"prompt": prompt, "steps": steps}, timeout=180)
    check_http(resp)
    image = (resp.json().get("result") or {}).get("image")
    if not image:
        raise RuntimeError(f"no image in response: {resp.text[:300]}")
    return base64.b64decode(image)


def generate(sb, *, item_id, prompt, seed, out_path, key=None) -> float:
    m = sb["models"]["keyframes"]
    params = {"steps": m["steps"], "size": "1024x1024", "prompt": prompt}
    ctx = dict(stage=STAGE, provider=m["provider"], model=m["model"], shot_id=item_id,
               params=params, seed=seed, cache_key=key)
    img, latency, attempt = with_retries(lambda: cf_generate(m["model"], prompt, seed, m["steps"]), log_ctx=ctx)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img)
    log_run(**ctx, latency_s=latency, output=rel(out_path), attempt=attempt)
    return latency


def run(only=None, force=False) -> None:
    load_env()
    sb = load_storyboard()
    manifest = Manifest(STAGE)
    for shot in select_shots(sb, only):
        key = expected_key(sb, shot)
        if not force and manifest.valid(shot["id"], key):
            print(f"  {shot['id']}: cached")
            continue
        out = OUTPUTS / STAGE / f"{shot['id']}_{key[:10]}.png"
        prompt = build_prompt(sb, shot)
        try:
            latency = generate(sb, item_id=shot["id"], prompt=prompt, seed=shot["keyframe"]["seed"], out_path=out, key=key)
        except Exception as e:
            print(f"  {shot['id']}: FAILED ({e}). Assembly will use a placeholder card; see FAILURES.md")
            continue
        manifest.set(shot["id"], key=key, path=rel(out), seed=shot["keyframe"]["seed"], prompt=prompt)
        print(f"  {shot['id']}: generated in {latency:.1f}s -> {rel(out)}")


def reference_sheets(n: int) -> None:
    load_env()
    sb = load_storyboard()
    for name, ref in sb["references"].items():
        base = ref.get("approved_seed") or 500
        for i in range(n):
            seed = base + i
            out = OUTPUTS / "reference" / f"{name}_seed{seed}.png"
            if out.exists():
                continue
            generate(sb, item_id=f"ref:{name}", prompt=f"{ref['sheet_prompt']}. {sb['style_block']}", seed=seed, out_path=out)
            print(f"  {name} seed {seed} -> {rel(out)}")
    print("Pick the best of each, put its seed in references.<name>.approved_seed, note why in EXPERIMENTS.md.")


def candidates(only, n: int) -> None:
    load_env()
    sb = load_storyboard()
    for shot in select_shots(sb, only):
        prompt = build_prompt(sb, shot)
        for i in range(n):
            seed = shot["keyframe"]["seed"] + 1000 * (i + 1)
            out = OUTPUTS / STAGE / "candidates" / f"{shot['id']}_seed{seed}.png"
            if out.exists():
                continue
            generate(sb, item_id=shot["id"], prompt=prompt, seed=seed, out_path=out)
            print(f"  {shot['id']} seed {seed} -> {rel(out)}")
    print("Copy the seed you prefer into shots[].keyframe.seed and rerun the stage.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--candidates", type=int, default=0)
    a = ap.parse_args()
    t0 = time.time()
    if a.sheet:
        reference_sheets(4)
    elif a.candidates:
        candidates(a.only, a.candidates)
    else:
        run(a.only, a.force)
    print(f"keyframes stage done in {time.time() - t0:.1f}s")
