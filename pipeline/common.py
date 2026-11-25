"""Shared helpers used by every stage: storyboard loading, content hashing,
per-stage manifests (the cache), run logging to runs.jsonl, retries and ffmpeg."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import random
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
OUTPUTS = ROOT / "outputs"
BUILD = ROOT / "build"
RUNS = ROOT / "runs.jsonl"


# ---------------------------------------------------------------- config / secrets
def load_env() -> None:
    """Secrets live in .env (git-ignored), never in the repo."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def env(name: str, default: str | None = None, required: bool = True) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return value


# ---------------------------------------------------------------- storyboard
def load_storyboard(validate: bool = True) -> dict:
    sb = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    if validate:
        from pipeline.validate import validate_storyboard
        validate_storyboard(sb)
    return sb


def save_storyboard(sb: dict) -> None:
    STORYBOARD.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def select_shots(sb: dict, only: list[str] | None) -> list[dict]:
    if not only:
        return sb["shots"]
    wanted = set(only)
    missing = wanted - {s["id"] for s in sb["shots"]}
    if missing:
        raise SystemExit(f"Unknown shot id(s): {', '.join(sorted(missing))}")
    return [s for s in sb["shots"] if s["id"] in wanted]


# ---------------------------------------------------------------- hashing / cache
def stable_hash(obj) -> str:
    """Hash of a stage's inputs. Same inputs -> same key -> cached output is reused."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def file_hash(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: pathlib.Path | str) -> str:
    return str(pathlib.Path(path).resolve().relative_to(ROOT))


class Manifest:
    """outputs/<stage>/manifest.json maps shot id -> {key, path, ...}.
    An entry is valid only if its key equals the key computed from the current storyboard."""

    def __init__(self, stage: str):
        self.dir = OUTPUTS / stage
        self.path = self.dir / "manifest.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def get(self, item_id: str) -> dict | None:
        return self.data.get(item_id)

    def valid(self, item_id: str, key: str) -> dict | None:
        e = self.data.get(item_id)
        if e and e.get("key") == key and (ROOT / e["path"]).exists():
            return e
        return None

    def set(self, item_id: str, **entry) -> None:
        self.data[item_id] = entry
        self.save()

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- run log
def log_run(stage: str, provider: str, model: str, *, shot_id=None, params=None, seed=None,
            latency_s=None, status="ok", cache_key=None, output=None, error=None,
            gpu_minutes=None, **extra) -> None:
    """One line per model call (including failed attempts) in runs.jsonl."""
    rec = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "stage": stage, "shot_id": shot_id, "provider": provider, "model": model,
        "params": params or {}, "seed": seed,
        "latency_s": None if latency_s is None else round(latency_s, 3),
        "gpu_minutes": None if gpu_minutes is None else round(gpu_minutes, 3),
        "status": status, "cache_key": cache_key[:16] if cache_key else None,
        "output": output, "error": error,
    }
    rec.update(extra)
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- retries
class RetryableError(Exception):
    """Quota, rate-limit or transient server errors."""


def check_http(resp) -> None:
    if resp.status_code in (408, 429, 500, 502, 503, 504):
        raise RetryableError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")


def with_retries(call, *, log_ctx: dict, attempts: int = 3, base_delay: float = 5.0):
    """Run call() up to `attempts` times with exponential backoff on RetryableError.
    Every failed attempt is logged; the caller logs the success (it knows the output)."""
    for attempt in range(1, attempts + 1):
        t0 = time.time()
        try:
            return call(), time.time() - t0, attempt
        except RetryableError as e:
            last = attempt == attempts
            log_run(**log_ctx, latency_s=time.time() - t0, status="error" if last else "retry",
                    error=str(e)[:500], attempt=attempt)
            if last:
                raise
            delay = base_delay * 2 ** (attempt - 1) + random.uniform(0, 1)
            print(f"    retryable error ({e.__class__.__name__}), waiting {delay:.0f}s")
            time.sleep(delay)
        except Exception as e:  # not retryable: log and surface
            log_run(**log_ctx, latency_s=time.time() - t0, status="error", error=str(e)[:500], attempt=attempt)
            raise


# ---------------------------------------------------------------- ffmpeg
def ffmpeg(*args, capture: bool = False) -> str:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-loglevel", "info" if capture else "error", *map(str, args)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd) + "\n" + proc.stderr[-2000:])
    return proc.stderr


def probe_duration(path: pathlib.Path | str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def find_font(pattern: str, must_contain: str | None = None) -> str | None:
    try:
        path = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return None
    if not path or (must_contain and must_contain.lower() not in path.lower()):
        return None
    return path
