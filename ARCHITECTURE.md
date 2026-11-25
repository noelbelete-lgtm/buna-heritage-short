# Architecture

## One contract, five stages

`storyboard.json` is the only input every stage reads. It holds the film settings, model choices, a fixed style block, reference descriptions, 10 shots (prompt, seed, motion, narration in Amharic and English, reason, music cue) and the music spec. `schema/storyboard.schema.json` (JSON Schema 2020-12) is checked before every run, plus semantic checks in `pipeline/validate.py`: unique shot ids, known references and cues, planned duration inside 60–90 s, an end card that says "Made with AI".

| stage | script | model / tool | where it runs | output |
|---|---|---|---|---|
| keyframes | `pipeline/keyframes.py` | FLUX.1 schnell (Workers AI) | Cloudflare API | `outputs/keyframes/<shot>_<key>.png` |
| narration | `pipeline/narration.py` | Gemini Flash TTS | Gemini API | `outputs/narration/<shot>_<key>.wav` |
| shots | `pipeline/shots.py` + `notebooks/kaggle_wan22_i2v.py` | Wan 2.2 TI2V-5B | Kaggle T4 ×2 | `outputs/shots/<shot>_<key>.mp4` |
| music | `pipeline/music.py` + `notebooks/kaggle_acestep.py` | ACE-Step 1.5 | Kaggle T4 | `outputs/music/candidates/*.wav` |
| assemble | `pipeline/assemble.py` | FFmpeg | local | `outputs/film/buna_9x16.mp4`, `buna_16x9.mp4`, `subtitles_en.srt` |

`pipeline/run.py` chains them (`make film`).

## Caching: only what changed is regenerated

Each stage computes a **key** = SHA-256 of exactly the inputs that determine its output:

- keyframe: model, steps, full prompt (shot prompt + reference descriptions + style block), seed, size
- narration: TTS model, voice, style instruction, Amharic text
- clip: the keyframe's key, motion prompt, negative prompt, seed, Wan settings
- edit piece: hash of the source file, shot length, aspect, camera move, on-screen text

Outputs are named `<shot>_<key[:10]>` and recorded in `outputs/<stage>/manifest.json`. An entry counts only if its key equals the key computed from the *current* storyboard and the file exists. Keys chain: changing a keyframe prompt changes the keyframe key, which changes the expected clip key, so the old clip is ignored automatically and that shot falls back to Ken Burns until Wan re-renders it. Changing a narration line touches only that shot's audio and edit piece.

Gemini TTS has no seed, so the cache is also what makes narration reproducible: a re-run reuses the approved take instead of rolling a new one.

## Failure handling

- `with_retries` retries HTTP 408/429/5xx three times with exponential backoff plus jitter. Every failed attempt is a line in `runs.jsonl` (`status: retry|error`).
- A stage that fails for one shot logs it, prints a pointer to FAILURES.md and moves on to the next shot. Nothing aborts the whole run.
- Assembly degrades step by step: Wan clip → Ken Burns over the keyframe → a labelled placeholder card. Missing narration becomes silence; a missing score becomes the placeholder drone. The film always renders.
- Kaggle workers are resumable (finished clips are skipped), write a result line per job including OOM/errors, and shard jobs across both T4s.
- Clips are imported only if their key still matches the storyboard, so a stale download can never slip into the edit.

## Assembly

1. Timeline: shot length = max(planned duration, narration + 0.4 s lead + 0.6 s tail). The voice sets the cut.
2. Picture per shot, cropped from the centre to 1080×1920 or 1920×1080 (keyframes are square and centre-composed so both ratios come from one image). Clips have their first 0.25 s trimmed, are slowed at most 1.6× and then hold the last frame. Ken Burns uses `zoompan` on a 2× upscale to avoid jitter, with the camera move from the storyboard. Cup names are drawn with `drawtext` (text in code, never in the generated image).
3. End card (3.5 s): title, "Made with AI", model credits.
4. Audio: narration levelled to −16 LUFS, music to −24 LUFS; music ducked under the voice with `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms); a two-pass `loudnorm` to −14 LUFS integrated, −1 dBTP.
5. English subtitles generated from the storyboard (≤ 2 lines, ≤ 40 characters), timed to each line's measured audio and burned in inside the vertical safe area.
6. H.264 + AAC, 24 fps constant, `+faststart`.

## Logging

`runs.jsonl` has one line per model call: timestamp, stage, shot, provider, model, parameters, seed, latency, GPU minutes, status, cache key, output path, error. Kaggle results are imported into it with GPU name and minutes. `make report` turns it into the tables in COSTS.md.

## Secrets

Keys live in `.env` (git-ignored, template in `.env.example`) and are read from the environment. Nothing in the repo contains a key. Model ids that change often can be overridden by environment variable without editing the storyboard.

## Known limits

- FLUX.1 schnell on Workers AI takes no reference image, so consistency comes from the identical reference text and style block in every prompt, plus shots designed to avoid faces (hands, backs, objects). Switching to FLUX.2 klein with reference images is a planned experiment.
- Wan 2.2 5B on a T4 is slow and fp16-only; drafts run at 480×480, 73 frames (about 3 s), and only for shots where motion matters most.
