"""Stage 3: moving shots. Wan 2.2 image-to-video runs on a Kaggle GPU, so this stage has two halves:

  python -m pipeline.kaggle_bundle            # packs the jobs that are missing or stale
  ... run notebooks/kaggle_wan22_i2v.py on Kaggle, download clips.zip ...
  python -m pipeline.shots import path/to/clips   # verifies keys, copies clips, logs GPU time

A clip is only used if its key still matches the storyboard. Change a keyframe or motion prompt and
the old clip is ignored automatically; assembly falls back to a Ken Burns move until it is regenerated.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil

from pipeline import keyframes
from pipeline.common import OUTPUTS, Manifest, load_storyboard, log_run, rel, stable_hash

STAGE = "shots"


def expected_key(sb: dict, shot: dict) -> str | None:
    """None when the keyframe for this shot is missing or stale."""
    kf = Manifest("keyframes").valid(shot["id"], keyframes.expected_key(sb, shot))
    if not kf:
        return None
    v = sb["models"]["video"]
    return stable_hash({"keyframe_key": kf["key"], "motion": shot["motion"]["prompt"],
                        "negative": sb.get("negative_prompt", ""), "seed": shot["motion"]["seed"],
                        "model": v["model"], "w": v["width"], "h": v["height"],
                        "frames": v["num_frames"], "steps": v["steps"], "guidance": v["guidance"]})


def pending_jobs(sb: dict) -> list[dict]:
    manifest = Manifest(STAGE)
    jobs = []
    for shot in sb["shots"]:
        if shot["motion"]["method"] != "i2v":
            continue
        key = expected_key(sb, shot)
        if key is None or manifest.valid(shot["id"], key):
            continue
        kf = Manifest("keyframes").get(shot["id"])
        v = sb["models"]["video"]
        jobs.append({"shot_id": shot["id"], "key": key, "keyframe": pathlib.Path(kf["path"]).name,
                     "keyframe_path": kf["path"], "prompt": shot["motion"]["prompt"],
                     "negative": sb.get("negative_prompt", ""), "seed": shot["motion"]["seed"],
                     "model": v["model"], "width": v["width"], "height": v["height"],
                     "num_frames": v["num_frames"], "steps": v["steps"], "guidance": v["guidance"]})
    return jobs


def import_clips(folder: str) -> None:
    folder = pathlib.Path(folder)
    sb = load_storyboard()
    current = {s["id"]: expected_key(sb, s) for s in sb["shots"]}
    manifest = Manifest(STAGE)
    results = [json.loads(line) for f in sorted(folder.rglob("results_gpu*.jsonl")) for line in f.read_text().splitlines() if line.strip()]
    if not results:
        raise SystemExit(f"No results_gpu*.jsonl found under {folder}")
    logged = {(e.get("shot_id"), e.get("cache_key")) for e in _runs_for(STAGE)}
    for r in results:
        sid, key = r["shot_id"], r["key"]
        if (sid, key[:16]) not in logged:
            log_run(STAGE, "kaggle", r.get("model", sb["models"]["video"]["model"]), shot_id=sid,
                    params=r.get("params", {}), seed=r.get("seed"), latency_s=r.get("latency_s"),
                    gpu_minutes=(r.get("latency_s") or 0) / 60, status=r.get("status", "ok"),
                    cache_key=key, error=r.get("error"), gpu=r.get("gpu_name"), output=r.get("file"))
        if r.get("status") != "ok":
            print(f"  {sid}: {r.get('status')} on Kaggle ({(r.get('error') or '')[:80]})")
            continue
        if current.get(sid) != key:
            print(f"  {sid}: clip is stale (storyboard changed since export), skipped")
            continue
        src = next(folder.rglob(r["file"]), None)
        if not src:
            print(f"  {sid}: {r['file']} missing from download")
            continue
        dst = OUTPUTS / STAGE / f"{sid}_{key[:10]}.mp4"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest.set(sid, key=key, path=rel(dst), latency_s=r.get("latency_s"), seed=r.get("seed"))
        print(f"  {sid}: imported ({r.get('latency_s', 0) / 60:.1f} GPU min)")


def _runs_for(stage: str) -> list[dict]:
    from pipeline.common import RUNS
    if not RUNS.exists():
        return []
    return [e for e in map(json.loads, RUNS.read_text(encoding="utf-8").splitlines()) if e.get("stage") == stage]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending", help="list shots that still need a clip")
    imp = sub.add_parser("import")
    imp.add_argument("folder")
    a = ap.parse_args()
    if a.cmd == "pending":
        for j in pending_jobs(load_storyboard()):
            print(f"  {j['shot_id']}  key={j['key'][:10]}  {j['prompt'][:60]}")
    else:
        import_clips(a.folder)
