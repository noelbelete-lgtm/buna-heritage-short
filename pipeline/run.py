"""One entry point for the whole pipeline.

  python -m pipeline.run all      # validate -> keyframes -> narration -> (clips) -> assemble both ratios
  python -m pipeline.run radio    # validate -> narration -> radio cut
  python -m pipeline.run status   # what is cached, stale or missing for every shot

Every stage is cached by a hash of its inputs, so re-running after editing one shot in
storyboard.json makes exactly the model calls that shot needs and nothing else.
"""
from __future__ import annotations

import sys
import time

from pipeline import assemble, keyframes, narration, shots
from pipeline.common import RUNS, Manifest, load_storyboard


def _count_runs() -> int:
    return sum(1 for _ in RUNS.open(encoding="utf-8")) if RUNS.exists() else 0


def status() -> None:
    sb = load_storyboard()
    km, nm, sm = Manifest("keyframes"), Manifest("narration"), Manifest("shots")
    print(f"{'shot':5} {'keyframe':9} {'narration':10} {'clip':10} -> used in edit")
    for s in sb["shots"]:
        kf = "ok" if km.valid(s["id"], keyframes.expected_key(sb, s)) else ("stale" if km.get(s["id"]) else "missing")
        na = "ok" if nm.valid(s["id"], narration.expected_key(sb, s)) else ("stale" if nm.get(s["id"]) else "missing")
        ck = shots.expected_key(sb, s)
        cl = "ok" if ck and sm.valid(s["id"], ck) else ("stale" if sm.get(s["id"]) else "missing")
        used = "wan clip" if cl == "ok" and s["motion"]["method"] == "i2v" else ("ken burns" if kf == "ok" else "placeholder")
        print(f"{s['id']:5} {kf:9} {na:10} {cl:10} -> {used}")
    music = sb["music"].get("selected") or "placeholder (no score selected yet)"
    print(f"music: {music}")


def main(cmd: str) -> None:
    t0, before = time.time(), _count_runs()
    from pipeline.validate import validate_storyboard
    print("[1/5] validate:", validate_storyboard(load_storyboard(validate=False)))
    if cmd == "radio":
        print("[2/5] narration"); narration.run()
        print("[5/5] radio cut"); assemble.radio_cut()
    elif cmd == "all":
        print("[2/5] keyframes"); keyframes.run()
        print("[3/5] narration"); narration.run()
        print("[4/5] clips (Wan 2.2 runs on Kaggle):")
        pend = shots.pending_jobs(load_storyboard())
        print("  all clips current" if not pend else
              f"  {len(pend)} shot(s) without a current clip will use Ken Burns: {', '.join(j['shot_id'] for j in pend)}"
              "\n  (python -m pipeline.kaggle_bundle to send them to Kaggle)")
        print("[5/5] assemble"); assemble.film(list(assemble.ASPECTS))
    elif cmd == "status":
        status(); return
    else:
        raise SystemExit(__doc__)
    print(f"done in {time.time() - t0:.0f}s, {_count_runs() - before} new line(s) in runs.jsonl")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
