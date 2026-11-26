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
| keyframes | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 30 | 30 | 0 | 8.8 | 4.5 | 0.0 | n/a |
| music | kaggle | `ACE-Step 1.5 turbo (no LM planner)` | 3 | 3 | 0 | 7.9 | 0.4 | 0.4 | n/a |
| narration | gemini | `gemini-3.8-flash-lite-tts` | 10 | 10 | 0 | 12.9 | 2.1 | 0.0 | n/a |
| narration | gemini | `gemini-3.8-flash-tts` | 65 | 14 | 51 | 6.3 | 2.3 | 0.0 | n/a |
| narration-trim | local | `ffmpeg silencedetect` | 10 | 10 | 0 | 0.0 | 0.0 | 0.0 | n/a |
| shots | kaggle | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | 22 | 2 | 20 | 595.2 | 19.6 | 20.1 | n/a |
| smoke | cloudflare | `@cf/black-forest-labs/flux-2-klein-4b` | 1 | 1 | 0 | 8.5 | 0.1 | 0.0 | n/a |
| smoke | cloudflare | `image` | 1 | 0 | 1 | 0.0 | 0.0 | 0.0 | n/a |
| smoke | gemini | `gemini-3.5-flash-lite` | 1 | 1 | 0 | 21.1 | 0.4 | 0.0 | n/a |
| smoke | gemini | `gemini-3.8-flash-tts` | 1 | 1 | 0 | 3.7 | 0.1 | 0.0 | n/a |
| smoke | gemini | `text` | 1 | 0 | 1 | 0.0 | 0.0 | 0.0 | n/a |
| smoke | gemini | `tts` | 1 | 0 | 1 | 0.0 | 0.0 | 0.0 | n/a |

Total list-price equivalent: **$0.00** (rates in `pipeline/prices.json`). Actual spend: $0 (free tiers).
<!-- COSTS:END -->

List-price rates used and their sources (date checked) are in `pipeline/prices.json`.

## Notes

- Wan 2.2 model load time on Kaggle is logged separately (`model_load_s`) and is not counted per clip.
- Assembly is local FFmpeg; wall time per full render (both ratios):
- Frontier comparison: (only if org access to Omni Flash, Nano Banana or Lyria is provided)
