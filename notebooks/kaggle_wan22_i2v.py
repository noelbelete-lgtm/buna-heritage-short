"""Wan 2.2 TI2V-5B image-to-video worker for Kaggle (GPU T4).

What works on a 15 GB T4 (see FAILURES.md F7 and EXPERIMENTS.md E5):
  * model offload in fp16           -> OOM (14.4 GiB)
  * model offload + fp8 weights     -> OOM (14.5 GiB)
  * sequential offload (default)    -> ~1-1.5 GiB GPU, ~4.7 min denoising + ~5 min decode per clip
One process at a time: two model copies need more than the 31 GB of system RAM.

Kaggle notebook (Settings: Accelerator GPU T4 x2, Internet on; attach the dataset made from build/kaggle_jobs.zip):
  Cell 1:  !pip install -q "diffusers>=0.35" transformers accelerate ftfy imageio imageio-ffmpeg sentencepiece
  Cell 2:  import glob, subprocess
           w = glob.glob('/kaggle/input/**/kaggle_wan22_i2v.py', recursive=True)[0]
           subprocess.Popen(f"python {w} --gpu 0 > /kaggle/working/wan.log 2>&1", shell=True)
  Cell 3 (watch, re-run):  !tail -n 4 /kaggle/working/wan.log; ls /kaggle/working/clips
  Cell 4 (download, re-run as clips finish):
           !cd /kaggle/working && rm -f clips.zip && zip -qr clips.zip clips
           from IPython.display import FileLink; FileLink('clips.zip')
  Locally: unzip, then  make import-shots DIR=path/to/clips  &&  make film
Resumable: finished clips are skipped if the session restarts.
"""
import argparse, gc, glob, json, os, pathlib, time

ap = argparse.ArgumentParser()
ap.add_argument("--gpu", type=int, default=0)
ap.add_argument("--shard", type=int, default=0)
ap.add_argument("--nshards", type=int, default=1)
ap.add_argument("--offload", choices=["model", "sequential"], default="sequential")
ap.add_argument("--fp8", action="store_true", help="fp8 weight storage (only with --offload model)")
ap.add_argument("--out", default="/kaggle/working/clips")
a = ap.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = str(a.gpu)          # before torch is imported
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
from diffusers.utils import export_to_video, load_image

jobs_file = pathlib.Path(glob.glob("/kaggle/input/**/jobs.json", recursive=True)[0])
jobs = json.loads(jobs_file.read_text())["jobs"][a.shard::a.nshards]
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
results = out / f"results_gpu{a.gpu}_{a.offload}.jsonl"
print(f"GPU {a.gpu}: {len(jobs)} job(s)", flush=True)
if not jobs:
    print("DONE", flush=True); raise SystemExit

model_id = jobs[0]["model"]
t = time.time()
vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
pipe = WanImageToVideoPipeline.from_pretrained(model_id, vae=vae, torch_dtype=torch.float16)
fp8 = False
if a.fp8 and a.offload == "model":
    pipe.transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=torch.float16)
    fp8 = True
if a.offload == "sequential":
    pipe.enable_sequential_cpu_offload()
else:
    pipe.enable_model_cpu_offload()
pipe.vae.enable_tiling()
load_s = time.time() - t
gpu = torch.cuda.get_device_name(0)
print(f"model loaded in {load_s:.0f}s, fp8={fp8}, offload={a.offload}", flush=True)

for job in jobs:
    name = f"{job['shot_id']}_{job['key'][:10]}.mp4"
    dst = out / name
    if dst.exists():
        print(f"{job['shot_id']}: already done", flush=True)
        continue
    image = load_image(str(jobs_file.parent / "keyframes" / job["keyframe"])).resize((job["width"], job["height"]))
    params = {k: job[k] for k in ("width", "height", "num_frames", "steps", "guidance")} | {
        "dtype": "fp16", "fp8_weights": fp8, "offload": a.offload}
    t0 = time.time(); status, err = "ok", None
    try:
        frames = pipe(image=image, prompt=job["prompt"], negative_prompt=job.get("negative", ""),
                      height=job["height"], width=job["width"], num_frames=job["num_frames"],
                      num_inference_steps=job["steps"], guidance_scale=job["guidance"],
                      generator=torch.Generator("cpu").manual_seed(job["seed"])).frames[0]
        export_to_video(frames, str(dst), fps=24)
    except torch.cuda.OutOfMemoryError as e:
        status, err = "oom", str(e)[:300]
    except Exception as e:
        status, err = "error", f"{type(e).__name__}: {e}"[:300]
    gc.collect(); torch.cuda.empty_cache()                # free memory so one failure does not cascade
    rec = {"shot_id": job["shot_id"], "key": job["key"], "file": name, "status": status, "error": err,
           "latency_s": round(time.time() - t0, 1), "seed": job["seed"], "model": model_id, "params": params,
           "gpu_name": gpu, "model_load_s": round(load_s, 1)}
    with results.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"{job['shot_id']}: {status} in {rec['latency_s'] / 60:.1f} min {err or ''}"[:200], flush=True)
print("DONE", flush=True)
