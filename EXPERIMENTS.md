# Experiments

One change at a time, seed fixed unless the experiment is about the seed. Evidence lives in `runs.jsonl` (search by shot id or timestamp) and in the files named in each entry.

Format:

```
## E<n>: <short title>   (date, stage)
Hypothesis:
Change:              (exactly what was changed in storyboard.json or code)
Held fixed:
Result:              (what happened, with numbers where possible: latency, words/s, LUFS, number of retries)
Evidence:            (runs.jsonl lines, output files)
Decision:
```

## Planned (not yet run; delete each line once it becomes a real entry)

- Keyframes: style block in every prompt vs the shot prompt alone, same seed. Does the palette hold across s02, s05 and s09?
- Keyframes: 4 seeds for s05 (`--candidates 4`). How many have usable hands and pour geometry?
- Keyframes: steps 4 vs 8 on FLUX.1 schnell. Is the visible quality difference worth the latency?
- Keyframes: FLUX.1 schnell vs FLUX.2 klein on the same prompt and seed.
- Narration: voice A vs voice B for Amharic. Have a native speaker rate pronunciation of ቄጤማ, ረከቦት and በረካ.
- Narration: with vs without the style instruction. Measure words per second and get listener preference.
- Narration: one long call vs one call per shot. Compare timing control and re-take cost.
- Video: Wan at 480 vs 704 px. GPU minutes vs visible gain.
- Video: motion prompt with re-described subject vs motion-and-camera only. Watch for identity drift.
- Music: 3 ACE-Step seeds auditioned under the narration at low volume; choose one and say why.
- Music: caption with tempo inside vs tempo in the bpm field only.
- Mix: ducking at ratio 6 vs 10. Is the narration intelligible on a phone speaker?


## E1: Shorter TTS style instruction   (25 Nov, narration)
Hypothesis: the long English style prompt is read aloud or adds pauses (6 of 10 lines ran at 0.4 words/s vs 1.0 for the others)
Change:     style "Read the following Amharic text aloud in a calm, warm, unhurried voice, like an elder telling a story to family:" -> "Say calmly and warmly:"
Held fixed: voice Kore, model gemini-3.8-flash-tts, same Amharic text
Result:     s01 17.0s -> 7.0s (0.41 -> 1.00 words/s), s02 16.8s -> 7.3s (0.36 -> 0.82 words/s); lines now match the normal ones
Evidence:   runs.jsonl narration lines for s01 and s02, 25 Nov
Decision:   keep the short style instruction

## E3: Reference sheet selection   (25 Nov, keyframes)
Hypothesis: one approved reference per character/prop gives a fixed target to check every keyframe against
Change:     generated 4 seeds (500-503) per reference with flux-2-klein-4b
Result:     chose seed 503 for woman, jebena and rekebot because (your reason: closest to a real jebena, dress border clearest, ...)
Evidence:   outputs/reference/*_seed503.png
Decision:   approved_seed 503 recorded in storyboard.json; keyframes are checked against these by eye

## E4: Re-rolling weak keyframes by seed   (25 Nov, keyframes)
Hypothesis: s07 and s08 look unrealistic because of an unlucky seed, not the prompt
Change:     4 extra seeds each for s07 and s08 (--candidates 4), prompt and style unchanged
Held fixed: flux-2-klein-4b, 4 steps, same prompt and style block
Result:     none of the 8 candidates was clearly better than the originals
Evidence:   outputs/keyframes/candidates/s07_seed*.png, s08_seed*.png; runs.jsonl 25 Nov
Decision:   kept original seeds 1107 and 1108; if they still look weak as video, rewrite the prompt instead of re-rolling

## E5: Fitting Wan 2.2 TI2V-5B on a 15 GB T4   (25 Nov, shots)
Hypothesis: offloading strategy, not resolution, decides whether Wan 5B fits a T4
Change:     model offload (fp16) -> model offload + fp8 weights -> sequential offload
Held fixed: 480x480, 73 frames, 25 steps, guidance 5.0, seed per shot
Result:     model offload: OOM at 14.4 GiB; + fp8: still OOM at 14.5 GiB;
            sequential: 1.4 GiB GPU memory, 25 steps in 4m42s (11.3 s/step), model load 114 s
Evidence:   clips/results_gpu0.jsonl, results_gpu0_r2.jsonl (OOM records), wan3.log
Decision:   sequential offload for all clips; ~5-6 min per clip on one T4

## E6: Narration-driven shot length   (25 Nov, assembly)
Hypothesis: the pauses Natnael heard are the planned shot length exceeding the trimmed narration
Change:     shot length max(planned, voice+1.0s) -> max(4s, voice+0.7s); lead 0.4->0.25s, tail 0.6->0.45s
Held fixed: same narration files, same keyframes, same music
Result:     film 79.6s -> (new length)s; (your listening note)
Decision:
Result:     79.6s -> 61.7s (too close to the 60s floor) -> ~67s with 0.8s tail and a 2.5s hold on s10;
            voice now flows without long stops (your listening note)
Decision:   keep 0.3s lead / 0.8s tail, plus a 2.5s hold on the final shot for the ending

## E7: Choosing the score from 3 ACE-Step candidates   (25 Nov, music)
Hypothesis: different seeds of the same caption give clearly different scores; one will sit better under Amharic narration
Change:     3 seeds (301, 302, 303), same caption, 72 bpm, 85 s, 8 turbo steps, no LM planner
Held fixed: caption, bpm, duration, model (ACE-Step 1.5 turbo on a Kaggle T4, Python 3.12 venv)
Result:     ~8 s per track on a T4. 301: (your note); 302: (your note); 303: (your note)
Evidence:   outputs/music/candidates/*.wav, runs.jsonl music lines
Decision:   cand_seed301, because (your reason)

## E8: Cutting the spoken style prompt off the narration   (25 Nov, narration)
Hypothesis: the English prompt the TTS reads aloud ends at the first pause, so cutting there removes it cleanly
Change:     pipeline/trim_lead.py: ffmpeg silencedetect (-35 dB, >=0.2 s pause within the first 3 s), cut before it
Held fixed: the 10 lite-TTS narration files (originals kept in outputs/narration/untrimmed/)
Result:     cut 2.30-2.93 s per line (mean 2.6 s); no English left; no Amharic lost on listening
Evidence:   outputs/narration/manifest.json (trimmed_s), runs.jsonl narration-trim lines
Decision:   keep; 0 API calls, which mattered with the TTS quota exhausted

## E9: Hitting -14 LUFS / -1 dBTP after AAC encoding   (26 Nov, assembly)
Hypothesis: two-pass loudnorm to -14 LUFS / -1 dBTP is enough for platform delivery
Change:     measured each stage with pipeline/diag_audio.py, then tested encoder settings on the same mix
Result:     the mix was clean (true peak -1.7 dBFS) but the AAC encode overshot to +4.0 dBFS.
            limiter -2 dB alone: film still +1.5; lowpass 16 kHz: +1.9; twoloop coder: +4.0;
            lowpass + twoloop + 256 kbps: -0.3; + limiter -4 dB: -1.2 dBFS at -14.6 LUFS; limiter -5 dB: -1.0 at -15.0
Evidence:   build/audio_diag test files; ebur128 measurements on outputs/film/buna_9x16.mp4
Decision:   limiter -4 dB + 16 kHz lowpass + twoloop AAC 256 kbps; final film I = ___ LUFS, true peak = ___ dBFS

## E10: A stronger ending line (Dibora's feedback)   (26 Nov, narration)
Hypothesis: one extra sentence aimed at the diaspora audience makes the ending land harder
Change:     s10 narration + "ከቤት ርቀን ስንሄድ የምንናፍቀውም ይህንኑ ነው።" ("When we are far from home, this is what we miss.")
Held fixed: all other shots, voice, style, music; regenerated with --only s10
Result:     make status showed only s10 stale; 1 TTS call (11.3 s audio, trimmed 2.74 s); film 68.2 s -> 73.0 s;
            (your note on how the ending feels now)
Evidence:   runs.jsonl narration line for s10, 26 Nov
Decision:   keep; test the effect in user test 2