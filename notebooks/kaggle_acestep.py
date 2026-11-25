"""ACE-Step 1.5 score candidates for Kaggle (one T4 is plenty; run it on GPU 1 while Wan uses GPU 0,
or in its own session).

Setup in the same Kaggle notebook (Internet on):
  1. Cell:
       !git clone -q https://github.com/ACE-Step/ACE-Step-1.5 /kaggle/working/ace && pip install -q -e /kaggle/working/ace
  2. Cell:
       import glob, subprocess
       w = glob.glob('/kaggle/input/**/kaggle_acestep.py', recursive=True)[0]
       subprocess.run(f"CUDA_VISIBLE_DEVICES=1 python {w}", shell=True)
  3. !cd /kaggle/working && zip -qr music.zip music   -> download
  4. Locally: python -m pipeline.music import path/to/music

generate() below is the ONLY function that touches ACE-Step. It is written against the pipeline API that
ACE-Step published (ACEStepPipeline). If 1.5 changed the entry point, open the repo README, adapt generate(),
and log what changed in FAILURES.md. Tempo and key go in their own fields, never in the caption.
"""
import glob
import json
import pathlib
import time

OUT = pathlib.Path("/kaggle/working/music")
_pipe = None


def generate(caption: str, lyrics: str, duration: float, bpm: int, key, seed: int, out_path: pathlib.Path) -> None:
    global _pipe
    if _pipe is None:
        from acestep.pipeline_ace_step import ACEStepPipeline  # check the 1.5 README if this import fails
        _pipe = ACEStepPipeline(checkpoint_dir=None, dtype="float16", torch_compile=False, cpu_offload=False)
    tags = caption + f", {bpm} bpm" + (f", {key}" if key else "")
    _pipe(format="wav", audio_duration=duration, prompt=tags, lyrics=lyrics, infer_step=60,
          guidance_scale=15.0, manual_seeds=[seed], save_path=str(out_path))


def main() -> None:
    job_file = glob.glob("/kaggle/input/**/music_job.json", recursive=True)[0]
    job = json.loads(pathlib.Path(job_file).read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    results = OUT / "results_music.jsonl"
    lyrics = "[instrumental]" if job["instrumental"] or not job.get("lyrics") else job["lyrics"]
    try:
        import torch
        gpu = torch.cuda.get_device_name(0)
    except Exception:
        gpu = "unknown"
    for seed in job["seeds"]:
        name = f"cand_seed{seed}.wav"
        if (OUT / name).exists():
            continue
        t0 = time.time()
        status, err = "ok", None
        try:
            generate(job["caption"], lyrics, job["duration_s"], job["bpm"], job.get("key"), seed, OUT / name)
        except Exception as e:
            status, err = "error", f"{type(e).__name__}: {e}"[:400]
        rec = {"file": name, "seed": seed, "status": status, "error": err, "latency_s": round(time.time() - t0, 1),
               "model": job["model"], "gpu_name": gpu,
               "params": {"caption": job["caption"], "bpm": job["bpm"], "key": job.get("key"), "duration_s": job["duration_s"]}}
        with results.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"seed {seed}: {status} in {rec['latency_s']}s {err or ''}", flush=True)


if __name__ == "__main__":
    main()
