"""Stage 5: music. ACE-Step runs on Kaggle; candidates come back here and you choose one.

  python -m pipeline.music import path/to/music     # copy candidates, log GPU time
  python -m pipeline.music select cand_seed302.wav --reason "why this one"
  python -m pipeline.music placeholder              # temp track for the radio cut
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil

from pipeline.common import OUTPUTS, ffmpeg, load_storyboard, log_run, rel, save_storyboard, stable_hash

STAGE = "music"
PLACEHOLDER = OUTPUTS / STAGE / "placeholder.wav"


def job(sb: dict) -> dict:
    m = sb["music"]
    spec = {"caption": m["caption"], "lyrics": m.get("lyrics"), "instrumental": m["instrumental"],
            "bpm": m["bpm"], "key": m.get("key"), "duration_s": m["duration_s"], "seeds": m["seeds"],
            "model": sb["models"]["music"]["model"]}
    spec["key_hash"] = stable_hash(spec)
    return spec


def make_placeholder() -> pathlib.Path:
    """A soft two-note drone: enough to judge narration pacing in the radio cut."""
    if PLACEHOLDER.exists():
        return PLACEHOLDER
    PLACEHOLDER.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=196:duration=40",
           "-f", "lavfi", "-i", "sine=frequency=293.66:duration=40",
           "-filter_complex", "[0][1]amix=inputs=2,tremolo=f=0.2:d=0.4,lowpass=f=900,volume=0.4,"
                              "afade=t=in:d=3,afade=t=out:st=37:d=3,aresample=48000",
           "-ac", 2, PLACEHOLDER)
    return PLACEHOLDER


def import_candidates(folder: str) -> None:
    folder = pathlib.Path(folder)
    rows = [json.loads(l) for f in folder.rglob("results_music*.jsonl") for l in f.read_text().splitlines() if l.strip()]
    if not rows:
        raise SystemExit(f"No results_music*.jsonl under {folder}")
    dst_dir = OUTPUTS / STAGE / "candidates"
    dst_dir.mkdir(parents=True, exist_ok=True)
    from pipeline.shots import _runs_for
    seen = {e.get("output") for e in _runs_for(STAGE)}
    for r in rows:
        if r.get("file") not in seen:
            log_run(STAGE, "kaggle", r.get("model", "ACE-Step"), params=r.get("params", {}), seed=r.get("seed"),
                    latency_s=r.get("latency_s"), gpu_minutes=(r.get("latency_s") or 0) / 60,
                    status=r.get("status", "ok"), error=r.get("error"), gpu=r.get("gpu_name"), output=r.get("file"))
        if r.get("status") != "ok":
            print(f"  seed {r.get('seed')}: {r.get('status')}")
            continue
        src = next(folder.rglob(r["file"]), None)
        if src:
            shutil.copy2(src, dst_dir / src.name)
            print(f"  {src.name}: imported ({(r.get('latency_s') or 0):.0f}s)")
    print("Listen under the radio cut, then: python -m pipeline.music select <file> --reason '...'")


def select(name: str, reason: str) -> None:
    path = OUTPUTS / STAGE / "candidates" / name
    if not path.exists():
        raise SystemExit(f"{rel(path) if path.is_absolute() else path} not found")
    sb = load_storyboard()
    sb["music"]["selected"] = rel(path)
    sb["music"]["selection_reason"] = reason
    save_storyboard(sb)
    print(f"selected {rel(path)}; remember the EXPERIMENTS.md entry")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("import"); i.add_argument("folder")
    s = sub.add_parser("select"); s.add_argument("name"); s.add_argument("--reason", required=True)
    sub.add_parser("placeholder")
    a = ap.parse_args()
    if a.cmd == "import":
        import_candidates(a.folder)
    elif a.cmd == "select":
        select(a.name, a.reason)
    else:
        print(rel(make_placeholder()))
