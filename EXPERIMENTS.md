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
