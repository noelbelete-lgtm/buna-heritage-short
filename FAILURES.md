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