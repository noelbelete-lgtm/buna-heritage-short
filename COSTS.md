# Costs and latency

Measured from `runs.jsonl` with `make report`. Free-tier limits checked on (date):

| service | free limit found | notes |
|---|---|---|
| Gemini API (text, TTS) | | |
| Cloudflare Workers AI | | daily neuron allowance |
| Kaggle | | GPU hours per week, T4 ×2 |

## Measured per stage

<!-- COSTS:BEGIN -->
| stage | provider | model | calls | ok | failed/retried | median latency (s) | total latency (min) | GPU min | list-price equiv (USD) |
|---|---|---|---|---|---|---|---|---|---|

Total list-price equivalent: **$0.00** (rates in `pipeline/prices.json`). Actual spend: $0 (free tiers).
<!-- COSTS:END -->

List-price rates used and their sources (date checked) are in `pipeline/prices.json`.

## Notes

- Wan 2.2 model load time on Kaggle is logged separately (`model_load_s`) and is not counted per clip.
- Assembly is local FFmpeg; wall time per full render (both ratios):
- Frontier comparison: (only if org access to Omni Flash, Nano Banana or Lyria is provided)
