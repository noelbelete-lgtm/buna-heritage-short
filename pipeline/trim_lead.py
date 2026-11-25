"""Cut a spoken English style instruction off the start of narration files, with no API calls.

The TTS model sometimes reads the style prompt ("Say calmly and warmly:") aloud before the Amharic.
There is a short pause between the two, so we find the first pause in the first few seconds and keep
only what follows. Originals are kept in outputs/narration/untrimmed/ so nothing is lost.

  python -m pipeline.trim_lead --dry-run         # show where each file would be cut
  python -m pipeline.trim_lead                   # cut all shots
  python -m pipeline.trim_lead --only s03 s07    # cut only these
  python -m pipeline.trim_lead --restore         # put the originals back
"""
from __future__ import annotations

import argparse
import re
import shutil

from pipeline.common import ROOT, Manifest, ffmpeg, log_run, probe_duration

UNTRIMMED = ROOT / "outputs" / "narration" / "untrimmed"


def first_gap(path, max_lead: float, noise_db: int, min_gap: float) -> float | None:
    """End time of the first pause that starts after some speech and ends within max_lead seconds."""
    log = ffmpeg("-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_gap}", "-f", "null", "-", capture=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    for s, e in zip(starts, ends):
        if s > 0.4 and e <= max_lead:      # speech before the pause, and the pause comes early
            return e
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--max-lead", type=float, default=3.0, help="the instruction must end before this second")
    ap.add_argument("--noise", type=int, default=-35, help="silence threshold in dB")
    ap.add_argument("--gap", type=float, default=0.2, help="minimum pause length in seconds")
    a = ap.parse_args()
    m = Manifest("narration")
    ids = a.only or sorted(m.data)
    UNTRIMMED.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        e = m.get(sid)
        if not e:
            print(f"  {sid}: no narration yet")
            continue
        path = ROOT / e["path"]
        backup = UNTRIMMED / path.name
        if a.restore:
            if backup.exists():
                shutil.copy2(backup, path)
                m.set(sid, **{**e, "duration_s": round(probe_duration(path), 3), "trimmed_s": 0})
                print(f"  {sid}: restored")
            continue
        src = backup if backup.exists() else path        # always measure the original
        cut = first_gap(src, a.max_lead, a.noise, a.gap)
        if cut is None:
            print(f"  {sid}: no early pause found, left as is")
            continue
        before = probe_duration(src)
        if a.dry_run:
            print(f"  {sid}: would cut first {cut:.2f}s of {before:.1f}s")
            continue
        if not backup.exists():
            shutil.copy2(path, backup)
        tmp = path.with_suffix(".tmp.wav")
        ffmpeg("-i", backup, "-af", f"atrim=start={max(cut - 0.05, 0):.3f},asetpts=N/SR/TB,afade=t=in:d=0.05",
               "-ar", 48000, "-ac", 1, tmp)
        tmp.replace(path)
        after = probe_duration(path)
        m.set(sid, **{**e, "duration_s": round(after, 3), "trimmed_s": round(cut, 2)})
        log_run("narration-trim", "local", "ffmpeg silencedetect", shot_id=sid,
                params={"cut_s": round(cut, 2), "noise_db": a.noise, "gap_s": a.gap}, output=e["path"],
                note="post-process, no model call")
        print(f"  {sid}: cut {cut:.2f}s -> {after:.1f}s left")
    if not a.restore and not a.dry_run:
        print("Listen to a few files. If a cut went into the Amharic: python -m pipeline.trim_lead --restore --only sXX")


if __name__ == "__main__":
    main()
