"""Regenerate the measured tables in COSTS.md and the shot table in DESIGN.md from runs.jsonl and storyboard.json.
  python -m pipeline.report
"""
from __future__ import annotations

import collections
import json
import re

from pipeline.common import ROOT, RUNS, load_storyboard

PRICES = ROOT / "pipeline" / "prices.json"


def replace_block(path, tag: str, body: str) -> None:
    text = path.read_text(encoding="utf-8")
    pat = re.compile(rf"(<!-- {tag}:BEGIN -->)(.*?)(<!-- {tag}:END -->)", re.S)
    path.write_text(pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text), encoding="utf-8")


def costs_table() -> str:
    rows = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines()] if RUNS.exists() else []
    prices = json.loads(PRICES.read_text())
    agg = collections.defaultdict(lambda: {"calls": 0, "ok": 0, "fail": 0, "lat": [], "gpu": 0.0, "units": 0.0})
    for r in rows:
        a = agg[(r["stage"], r["provider"], r["model"])]
        a["calls"] += 1
        a["ok" if r["status"] == "ok" else "fail"] += 1
        if r.get("latency_s") is not None and r["status"] == "ok":
            a["lat"].append(r["latency_s"])
        a["gpu"] += r.get("gpu_minutes") or 0
        if r["status"] == "ok":
            a["units"] += r.get("audio_s", 1) if r["stage"] == "narration" else 1
    out = ["| stage | provider | model | calls | ok | failed/retried | median latency (s) | total latency (min) | GPU min | list-price equiv (USD) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    grand = 0.0
    for (stage, prov, model), a in sorted(agg.items()):
        lat = sorted(a["lat"])
        med = lat[len(lat) // 2] if lat else 0
        p = prices.get(f"{prov}:{model}") or prices.get(prov) or {}
        usd = None
        if p.get("usd") is not None:
            usd = p["usd"] * (a["gpu"] if p.get("unit") == "gpu_minute" else a["units"])
            grand += usd
        out.append(f"| {stage} | {prov} | `{model}` | {a['calls']} | {a['ok']} | {a['fail']} | {med:.1f} | "
                   f"{sum(lat) / 60:.1f} | {a['gpu']:.1f} | {'n/a' if usd is None else f'{usd:.3f}'} |")
    out.append(f"\nTotal list-price equivalent: **${grand:.2f}** (rates in `pipeline/prices.json`). Actual spend: $0 (free tiers).")
    return "\n".join(out)


def shots_table() -> str:
    sb = load_storyboard()
    out = ["| shot | size | beat | why it exists |", "|---|---|---|---|"]
    out += [f"| {s['id']} | {s['shot_size'].replace('_', ' ')} | {s['beat']} | {s['reason']} |" for s in sb["shots"]]
    return "\n".join(out)


if __name__ == "__main__":
    replace_block(ROOT / "COSTS.md", "COSTS", costs_table())
    replace_block(ROOT / "DESIGN.md", "SHOTS", shots_table())
    print("COSTS.md and DESIGN.md tables updated")
