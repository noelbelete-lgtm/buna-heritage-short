# Buna: The Three Cups (ቡና፡ ሦስቱ ስኒዎች)

A 60–90 second film about the Ethiopian coffee ceremony, narrated in Amharic with English subtitles and an original score, produced entirely by a code pipeline from one file: [`storyboard.json`](storyboard.json).

> In one afternoon coffee ceremony, three cups (abol, tona and bereka) carry a family's beginning, its conversation and its blessing.

## Run it

Requirements: Python 3.10+, FFmpeg 6+, a free Gemini API key, a free Cloudflare account.

```bash
git clone <this repo> && cd <repo>
make setup
cp .env.example .env        # add GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
make film                   # -> outputs/film/buna_9x16.mp4 and buna_16x9.mp4
```

`make film` validates the storyboard, generates any missing keyframes and narration, and assembles both aspect ratios. Everything already generated is reused from `outputs/` (it is committed), so on a clean clone it makes **zero model calls** and just re-edits the film.

Moving shots (Wan 2.2) and the score (ACE-Step 1.5) need a GPU, so they run on a free Kaggle T4 and are imported back:

```bash
make bundle                                   # build/kaggle_jobs.zip: only clips that are missing or stale
# run notebooks/kaggle_wan22_i2v.py and notebooks/kaggle_acestep.py on Kaggle (instructions inside each file)
make import-shots DIR=~/Downloads/clips
make import-music DIR=~/Downloads/music
python -m pipeline.music select cand_seed302.wav --reason "why"
make film
```

A shot without a current clip gets a slow Ken Burns move over its keyframe, so the film is always complete.

## Change one shot

Edit one narration line or keyframe prompt in `storyboard.json`, then:

```bash
make status    # shows exactly which shot is now stale
make film      # regenerates only that shot; check the tail of runs.jsonl for the single new call
```

## Other targets

| command | what it does |
|---|---|
| `make smoke` | calls each provider once and logs latency |
| `make sheet` | reference sheets for the woman, jebena and rekebot |
| `make radio` | radio cut: narration over temp music on black, subtitled |
| `make report` | refreshes measured tables in COSTS.md and the shot table in DESIGN.md |

## Pipeline

```
storyboard.json ──validate──┬─ keyframes  (FLUX, Cloudflare)     outputs/keyframes/
  (schema/)                 ├─ narration  (Gemini TTS, Amharic)  outputs/narration/
                            ├─ shots      (Wan 2.2, Kaggle T4)   outputs/shots/
                            ├─ music      (ACE-Step 1.5, Kaggle) outputs/music/
                            └─ assemble   (FFmpeg)               outputs/film/
every model call -> runs.jsonl
```

Details in [ARCHITECTURE.md](ARCHITECTURE.md). Audience and user tests in [DESIGN.md](DESIGN.md), experiments in [EXPERIMENTS.md](EXPERIMENTS.md), what broke in [FAILURES.md](FAILURES.md), measured cost in [COSTS.md](COSTS.md), consent and licences in [ETHICS.md](ETHICS.md).

## Cost

$0 spent. List-price equivalent and measured latency per stage are in [COSTS.md](COSTS.md).

## What actually ran (25-26 Nov 2026)

| stage | model | where | measured |
|---|---|---|---|
| keyframes | `@cf/black-forest-labs/flux-2-klein-4b` (Apache 2.0) | Cloudflare Workers AI, free | ~8-13 s per image |
| narration | `gemini-3.8-flash-lite-tts`, voice Kore | Gemini API free tier (3 req/min, 10 req/day) | 10 lines, 22 s pause between calls |
| shots | Wan 2.2 TI2V-5B, 480x480, 73 frames, 25 steps | Kaggle T4, sequential CPU offload | ~10 GPU min per clip, ~1.4 GB VRAM |
| music | ACE-Step 1.5 turbo, 8 steps, no LM planner | Kaggle T4, separate Python 3.12 venv | ~8 s per 85 s track |
| assembly | FFmpeg | local | ~1 min; film 68.2 s, -14.6 LUFS, -0.7 dBTP |

Helper tools: `python -m pipeline.list_models` (model ids your keys can use), `python -m pipeline.trim_lead` (cuts a spoken style prompt off TTS lines, no API calls), `python -m pipeline.diag_audio` (loudness and peak at every mix stage).

Things that differ from the brief: the Gemini model ids, FLUX.1 schnell rejecting seeds, Kaggle's Python 3.13, and the T4 memory limit. Each is in FAILURES.md with its fix.
