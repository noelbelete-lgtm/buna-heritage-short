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
