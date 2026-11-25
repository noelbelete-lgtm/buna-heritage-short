"""Wan 2.2 TI2V-5B image-to-video worker for Kaggle (GPU T4 x2).

Kaggle notebook setup (Settings -> Accelerator: GPU T4 x2, Internet: on, phone-verified account):
  1. Upload build/kaggle_jobs.zip as a Kaggle Dataset and attach it to the notebook.
  2. Cell 1:
       !pip install -q "diffusers>=0.35" transformers accelerate ftfy imageio imageio-ffmpeg sentencepiece
  3. Cell 2 (one worker per GPU, both in the background):
       import glob, subprocess
       w = glob.glob('/kaggle/input/**/kaggle_wan22_i2v.py', recursive=True)[0]
       for g in (0, 1):
           subprocess.Popen(f"python {w} --gpu {g} --shard {g} --nshards 2 > /kaggle/working/wan_gpu{g}.log 2>&1", shell=True)
  4. Cell 3 (re-run to watch progress):
       !tail -n 3 /kaggle/working/wan_gpu*.log; ls /kaggle/working/clips
  5. When both logs say DONE:
       !cd /kaggle/working && zip -qr clips.zip clips     -> download clips.zip from the Output panel
  6. Locally: unzip, then  python -m pipeline.shots import path/to/clips

The worker is resumable: if the session dies, re-run cell 2 and finished clips are skipped.
On a T4 there is no fast bf16, so it runs in fp16 with CPU offload. If clips come out black or noisy
(fp16 overflow), try --dtype fp32 on fewer frames, and record it in FAILURES.md.
"""
import argparse
import glob
import json
import os
import pathlib
import time


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--dtype", choices=["fp16", "fp32"], default="fp16")
    ap.add_argument("--out", default="/kaggle/working/clips")
    a = ap.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(a.gpu)   # must happen before torch is imported

    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    jobs_file = pathlib.Path(glob.glob("/kaggle/input/**/jobs.json", recursive=True)[0])
    jobs = json.loads(jobs_file.read_text())["jobs"][a.shard::a.nshards]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = out / f"results_gpu{a.gpu}.jsonl"
    print(f"GPU {a.gpu}: {len(jobs)} job(s)", flush=True)
    if not jobs:
        print("DONE", flush=True)
        return

    dtype = torch.float16 if a.dtype == "fp16" else torch.float32
    model_id = jobs[0]["model"]
    t_load = time.time()
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(model_id, vae=vae, torch_dtype=dtype)
    pipe.enable_model_cpu_offload()
    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass
    load_s = time.time() - t_load
    gpu_name = torch.cuda.get_device_name(0)
    print(f"model loaded in {load_s:.0f}s on {gpu_name}", flush=True)

    for job in jobs:
        name = f"{job['shot_id']}_{job['key'][:10]}.mp4"
        dst = out / name
        if dst.exists():
            print(f"{job['shot_id']}: already done", flush=True)
            continue
        image = load_image(str(jobs_file.parent / "keyframes" / job["keyframe"])).resize((job["width"], job["height"]))
        params = {k: job[k] for k in ("width", "height", "num_frames", "steps", "guidance")} | {"dtype": a.dtype}
        t0 = time.time()
        status, err = "ok", None
        try:
            frames = pipe(image=image, prompt=job["prompt"], negative_prompt=job.get("negative", ""),
                          height=job["height"], width=job["width"], num_frames=job["num_frames"],
                          num_inference_steps=job["steps"], guidance_scale=job["guidance"],
                          generator=torch.Generator("cpu").manual_seed(job["seed"])).frames[0]
            export_to_video(frames, str(dst), fps=24)
        except torch.cuda.OutOfMemoryError as e:
            status, err = "oom", str(e)[:400]
            torch.cuda.empty_cache()
        except Exception as e:
            status, err = "error", f"{type(e).__name__}: {e}"[:400]
        latency = time.time() - t0
        rec = {"shot_id": job["shot_id"], "key": job["key"], "file": name, "status": status, "error": err,
               "latency_s": round(latency, 1), "seed": job["seed"], "model": model_id, "params": params,
               "gpu_name": gpu_name, "model_load_s": round(load_s, 1)}
        with results.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{job['shot_id']}: {status} in {latency / 60:.1f} min", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
