"""Pack everything the Kaggle GPU needs into build/kaggle_jobs.zip:
pending Wan jobs + their keyframes, the music job, and both worker scripts.
Upload the zip as a Kaggle Dataset and attach it to a notebook (setup steps are in the docstring of each worker in notebooks/)."""
from __future__ import annotations

import json
import shutil

from pipeline import music, shots
from pipeline.common import BUILD, ROOT, load_storyboard


def main() -> None:
    sb = load_storyboard()
    out = BUILD / "kaggle_jobs"
    if out.exists():
        shutil.rmtree(out)
    (out / "keyframes").mkdir(parents=True)
    jobs = shots.pending_jobs(sb)
    for j in jobs:
        shutil.copy2(ROOT / j.pop("keyframe_path"), out / "keyframes" / j["keyframe"])
    (out / "jobs.json").write_text(json.dumps({"jobs": jobs}, indent=2, ensure_ascii=False))
    (out / "music_job.json").write_text(json.dumps(music.job(sb), indent=2, ensure_ascii=False))
    for f in ("kaggle_wan22_i2v.py", "kaggle_acestep.py"):
        shutil.copy2(ROOT / "notebooks" / f, out / f)
    archive = shutil.make_archive(str(BUILD / "kaggle_jobs"), "zip", out)
    print(f"{len(jobs)} video job(s): {', '.join(j['shot_id'] for j in jobs) or 'none (all clips up to date)'}")
    print(f"bundle: {archive}")


if __name__ == "__main__":
    main()
