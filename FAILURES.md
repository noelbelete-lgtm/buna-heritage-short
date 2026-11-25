# Failures

Every real blocker: quota, memory, consistency, language, tools that moved. Write it while it is fresh.

Format:

```
## F<n>: <what broke>   (date, stage)
Symptom:          (exact error or what you saw/heard; runs.jsonl line)
Cause:            (what you found, or best guess)
Tried:            (each attempt and what happened)
Resolution:       (fix, workaround, or fallback used)
Cost:             (time lost, GPU minutes, quota)
```

Things to watch for in this stack: Gemini TTS model id differs from the challenge brief; Amharic names mispronounced; Workers AI daily allowance exhausted; FLUX hands; Wan OOM or black frames in fp16 on T4; Kaggle session timeout; ACE-Step 1.5 entry point differs from the worker; subtitles covered by platform buttons.



## F1: Model ids in the brief did not exist   (25 Nov, smoke test)
Symptom:    HTTP 404 for gemini-3.8-flash-lite and gemini-3.8-flash-preview-tts
Cause:      the brief's model names differ from what the API serves to my key
Tried:      listed available models with pipeline/list_models.py
Resolution: TTS -> gemini-3.8-flash-tts, text -> gemini-3.5-flash-lite (no 3.8 lite exists)
Cost:       about 15 minutes, no quota used

## F2: FLUX.1 schnell rejected the seed parameter   (25 Nov, smoke test)
Symptom:    HTTP 400 "Additional or unevaluated properties '/seed' not allowed"
Cause:      schnell on Workers AI accepts only prompt and steps, so seeds can't be fixed
Tried:      removed seed from the request; listed Cloudflare text-to-image models
Resolution: switched to flux-2-klein-4b (Apache 2.0, accepts a seed) so experiments are reproducible
Cost:       about 10 minutes, 1 failed image call   


## F3: Gemini TTS quota and network errors   (25 Nov, narration)
Symptom:    HTTP 429 "You exceeded your current quota"; also DNS (NameResolutionError) and SSL EOF errors on some calls
Cause:      free tier for gemini-3.8-flash-tts is only 3 requests/min and 10 requests/day (AI Studio rate-limit page);
            the smoke test, two full regenerations and fast retries used up the daily quota; unstable connection
Tried:      retries raised to 5 with 15s backoff -> still 429 for 25 minutes (daily limit, not per-minute);
            re-runs reused cached lines so only failed shots were retried
Resolution: switched every line to gemini-3.8-flash-lite-tts (separate 10/day quota) so the voice stays consistent;
            22s pause between calls to respect 3/min; retries cut to 2 so failures don't waste the daily quota
Cost:       about 1.5 hours; the full daily TTS quota of one model
Lesson:     one full narration = 10 calls = a whole day's quota; change one line at a time with --only

## F4: TTS read the style instruction aloud   (25 Nov, narration)
Symptom:    every narration line starts with the English words "Say calmly and warmly"
Cause:      gemini-3.8-flash-lite-tts speaks the style prompt instead of following it (the long prompt did the same, see E1)
Tried:      a shorter prompt (E1) reduced it but did not stop it; regenerating without a prompt was impossible (both TTS models at 10/10 daily quota)
Resolution: pipeline/trim_lead.py finds the first pause with ffmpeg silencedetect and cuts everything before it; no API calls; originals kept in outputs/narration/untrimmed/
Cost:       about 30 minutes; 0 model calls
Next:       when the quota resets, regenerate with no style prompt and compare (planned E3)

## F5: Narration shown as stale after switching model   (25 Nov, pipeline)
Symptom:    make status showed all 10 narration lines "stale" although the files were fine
Cause:      the TTS model was overridden in .env, but status computed cache keys without reading .env,
            so it compared against the old model name in storyboard.json
Resolution: storyboard.json now records the model actually used (gemini-3.8-flash-lite-tts);
            narration.tts_model() loads .env before computing keys
Lesson:     anything that affects a cache key must live in storyboard.json, or a fresh clone regenerates everything

## F6: ACE-Step 1.5 would not install on Kaggle   (25 Nov, music)
Symptom:    "Package 'ace-step' requires a different Python: 3.13.16 not in '<3.13,>=3.11'",
            then "No matching distribution found for nano-vllm"
Cause:      Kaggle moved to Python 3.13; ACE-Step 1.5 pins Python 3.11-3.12, older torch/transformers,
            and the nano-vllm package used by its optional LM planner
Tried:      --ignore-requires-python (failed on nano-vllm); read run_generate_test.py to learn the real API
Resolution: installed with --no-deps, added its other requirements by hand (skipping torch/transformers so the
            running Wan job was not disturbed), and called generate_music() with thinking=False (no LM planner)
Cost:       about 30 minutes

## F7: Wan 2.2 out of memory on a T4   (25 Nov, shots)
Symptom:    s01 OOM after 15s ("14.38 GiB allocated by PyTorch" of 14.56); s02-s10 OOM instantly
Cause:      the 5B transformer in fp16 plus activations at 480x480x73 frames does not fit 15 GB even with model offload;
            memory was not released after the first OOM, so every later shot failed too
Tried:      reading the per-shot error in results_gpu0.jsonl and nvidia-smi
Resolution: fp8 weight storage (diffusers layerwise casting, compute stays fp16), expandable CUDA segments,
            free memory after every shot; one GPU at a time because two model copies need >31 GB RAM
Cost:       ~5 min model load + 15s GPU; 0 clips