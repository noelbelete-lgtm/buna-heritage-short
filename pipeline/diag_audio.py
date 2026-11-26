"""Measure loudness and peaks at each stage of the audio mix, to find where clipping appears."""
import pathlib, re
from pipeline import assemble as A
from pipeline.common import load_storyboard, ffmpeg
sb = load_storyboard(); items, sh = A.timeline(sb)
total = round(sh + sb["film"]["end_card"]["duration_s"], 3)
w = pathlib.Path("build/audio_diag"); w.mkdir(parents=True, exist_ok=True)
A.build_audio(sb, items, total, w, False)
def m(p):
    log = ffmpeg("-i", p, "-af", "ebur128=peak=true,astats=measure_overall=Peak_level:measure_perchannel=none", "-f", "null", "-", capture=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1]; tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)[-1]
    sp = re.findall(r"Peak level dB:\s+(-?[\d.]+)", log)
    print(f"{p.name:16} I={i} LUFS  truepeak={tp} dBFS  samplepeak={sp[-1] if sp else '?'} dB")
for n in ["narration.wav", "music.wav", "mix_raw.wav", "mix.wav"]:
    m(w / n)
ffmpeg("-i", w / "mix.wav", "-c:a", "aac", "-b:a", "192k", w / "mix.m4a"); m(w / "mix.m4a")
m(pathlib.Path("outputs/film/buna_9x16.mp4"))
