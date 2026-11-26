"""ACE-Step 1.5 score candidates on Kaggle (one T4, ~8 s per 85 s track with the turbo model).

Why the setup looks like this (see FAILURES.md F6):
  * Kaggle runs Python 3.13; ACE-Step 1.5 pins Python 3.11-3.12, torch 2.10+cu128 and transformers <4.58.
    Installing into Kaggle's own Python fails (version pin, nano-vllm) or loads with "meta tensors" errors.
  * So it runs in its own Python 3.12 venv made with uv, without the optional LM planner (thinking=False).
  * Kaggle sets MPLBACKEND to an inline backend that a separate interpreter cannot load -> MPLBACKEND=Agg.

Kaggle notebook (Accelerator GPU T4, Internet on, dataset from build/kaggle_jobs.zip attached):
  Cell 1 (setup, ~5-10 min):
    !pip install -q uv
    !git clone -q https://github.com/ACE-Step/ACE-Step-1.5 /kaggle/working/ace
    !uv venv -q /kaggle/working/py312 --python 3.12
    !cd /kaggle/working/ace && (uv pip install -q --python /kaggle/working/py312/bin/python -e . --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match || (grep -v -i nano requirements.txt > /tmp/req.txt && uv pip install -q --python /kaggle/working/py312/bin/python -r /tmp/req.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match && uv pip install -q --python /kaggle/working/py312/bin/python --no-deps -e .))
  Cell 2 (run):
    import glob, subprocess
    w = glob.glob('/kaggle/input/**/kaggle_acestep.py', recursive=True)[0]
    subprocess.Popen(f"MPLBACKEND=Agg /kaggle/working/py312/bin/python {w} > /kaggle/working/music.log 2>&1", shell=True)
  Cell 3 (watch):  !tail -n 8 /kaggle/working/music.log; ls /kaggle/working/music
  Cell 4 (download):
    !cd /kaggle/working && rm -f music.zip && zip -qr music.zip music -x "music/tmp_*"
    from IPython.display import FileLink; FileLink('music.zip')
  Locally: unzip, then  make import-music DIR=path/to/music  and  python -m pipeline.music select <file> --reason "..."
"""
import os, sys, json, time, glob, shutil, inspect, dataclasses, subprocess
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
os.environ["MPLBACKEND"] = "Agg"
ACE = "/kaggle/working/ace"
sys.path.insert(0, ACE); os.chdir(ACE)
import torch
from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

job = json.load(open(glob.glob('/kaggle/input/**/music_job.json', recursive=True)[0]))
OUT = "/kaggle/working/music"; os.makedirs(OUT, exist_ok=True)
gpu = torch.cuda.get_device_name(0)
t = time.time()
dit = AceStepHandler()
msg, ok = dit.initialize_service(project_root=ACE, config_path="acestep-v15-turbo", device="auto", offload_to_cpu=False)
print("model init:", ok, msg, f"{time.time()-t:.0f}s", flush=True)
if not ok:
    sys.exit(1)


def build(cls, **kw):
    """Pass only the fields this ACE-Step version accepts (the API moved between releases)."""
    names = {f.name for f in dataclasses.fields(cls)} if dataclasses.is_dataclass(cls) else set(inspect.signature(cls).parameters)
    return cls(**{k: v for k, v in kw.items() if k in names})


for seed in job["seeds"]:
    name = f"cand_seed{seed}.wav"
    if os.path.exists(f"{OUT}/{name}"):
        continue
    save = f"{OUT}/tmp_{seed}"; os.makedirs(save, exist_ok=True)
    params = build(GenerationParams, task_type="text2music", thinking=False, caption=job["caption"],
                   lyrics="[Instrumental]", instrumental=True, bpm=job["bpm"], keyscale=job.get("key") or "",
                   duration=job["duration_s"], inference_steps=8, guidance_scale=1.0, seed=seed, vocal_language="en")
    config = build(GenerationConfig, batch_size=1, audio_format="wav", save_dir=save, use_random_seed=False, seeds=[seed])
    available = {"dit_handler": dit, "llm_handler": None, "params": params, "config": config, "save_dir": save}
    kwargs = {k: v for k, v in available.items() if k in inspect.signature(generate_music).parameters}
    t0 = time.time(); status, err = "ok", None
    try:
        result = generate_music(**kwargs)
        files = [f for f in sorted(glob.glob(f"{save}/**/*", recursive=True), key=os.path.getmtime)
                 if f.endswith((".wav", ".flac", ".mp3"))]
        if not files:
            print("result:", str(result.to_dict() if hasattr(result, "to_dict") else result)[:800], flush=True)
            raise RuntimeError("no audio file written")
        if files[-1].endswith(".wav"):
            shutil.copy(files[-1], f"{OUT}/{name}")
        else:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", files[-1], f"{OUT}/{name}"], check=True)
    except Exception as e:
        status, err = "error", f"{type(e).__name__}: {e}"[:400]
    rec = {"file": name, "seed": seed, "status": status, "error": err, "latency_s": round(time.time() - t0, 1),
           "model": "ACE-Step 1.5 turbo (no LM planner)", "gpu_name": gpu,
           "params": {"caption": job["caption"], "bpm": job["bpm"], "duration_s": job["duration_s"], "steps": 8}}
    with open(f"{OUT}/results_music.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"seed {seed}: {status} in {rec['latency_s']}s {err or ''}", flush=True)
print("DONE", flush=True)
