"""Stage 6: assembly, all in FFmpeg and all from the storyboard.

  python -m pipeline.assemble --radio          # narration + temp music on black, with subtitles
  python -m pipeline.assemble                  # both aspect ratios
  python -m pipeline.assemble --aspect 9x16

Per shot: the Wan clip if its key is current, else a Ken Burns move over the keyframe, else a
placeholder card. Shot length = max(planned duration, narration + padding), so the voice sets the cut.
Audio: narration and music levelled separately, music ducked under the voice with sidechaincompress,
then a two-pass loudnorm to -14 LUFS / -1 dBTP. Subtitles are burned in inside the safe area.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import tempfile
import textwrap
import time

from pipeline import keyframes, music, narration, shots
from pipeline.common import (OUTPUTS, ROOT, Manifest, ffmpeg, file_hash, find_font, load_storyboard, probe_duration,
                             rel, stable_hash)

ASPECTS = {"9x16": (1080, 1920), "16x9": (1920, 1080)}
LEAD, TAIL = 0.3, 0.8  # silence before / after each narration line
EDIT = OUTPUTS / "edit"
FILM = OUTPUTS / "film"
LATIN_FONT = find_font("DejaVu Sans:bold") or find_font("sans:bold")
ETHIOPIC_FONT = find_font("Noto Sans Ethiopic:bold", must_contain="ethiopic") or find_font("Abyssinica SIL", must_contain="abyssinica")
SUB = {  # libass units are relative to a 288-line script, so sizes differ by aspect
    "9x16": "FontName=DejaVu Sans,Bold=1,FontSize=8,Outline=1.2,Shadow=0,MarginV=60,MarginL=14,MarginR=14,Alignment=2",
    "16x9": "FontName=DejaVu Sans,Bold=1,FontSize=13,Outline=1.5,Shadow=0,MarginV=18,Alignment=2",
    "radio": "FontName=DejaVu Sans,Bold=1,FontSize=13,Outline=1.5,Shadow=0,MarginV=24,Alignment=2",
}


# ---------------------------------------------------------------- timeline
def timeline(sb: dict) -> tuple[list[dict], float]:
    nm = Manifest("narration")
    items, t = [], 0.0
    for s in sb["shots"]:
        e = nm.valid(s["id"], narration.expected_key(sb, s))
        n = e["duration_s"] if e else 0.0
        dur = round((max(4.0, n + LEAD + TAIL) if n else s["duration_s"]) + (2.5 if s is sb["shots"][-1] else 0), 3)
        items.append({"shot": s, "start": round(t, 3), "dur": dur, "narr": (ROOT / e["path"]) if e else None, "narr_dur": n})
        t += dur
    return items, round(t, 3)


# ---------------------------------------------------------------- subtitles
def chunk_text(text: str, width: int = 40) -> list[str]:
    """Cues of at most two lines of ~40 characters."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    chunks, cur = [], ""
    for s in sentences:
        cand = f"{cur} {s}".strip()
        if len(textwrap.wrap(cand, width)) <= 2:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = s
            while len(textwrap.wrap(cur, width)) > 2:
                lines = textwrap.wrap(cur, width)
                chunks.append(" ".join(lines[:2]))
                cur = " ".join(lines[2:])
    if cur:
        chunks.append(cur)
    return ["\n".join(textwrap.wrap(c, width)) for c in chunks]


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(items: list[dict], path: pathlib.Path) -> None:
    cues = []
    for it in items:
        speech = it["narr_dur"] or max(1.5, it["dur"] - LEAD - TAIL)
        chunks = chunk_text(it["shot"]["narration"]["en"])
        total = sum(len(c) for c in chunks)
        t = it["start"] + LEAD
        for c in chunks:
            d = speech * len(c) / total
            cues.append((t, t + d, c))
            t += d
    path.write_text("\n".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{c}\n" for i, (a, b, c) in enumerate(cues, 1)),
                    encoding="utf-8")


# ---------------------------------------------------------------- audio
def build_narration(items: list[dict], total: float, out: pathlib.Path) -> None:
    inputs, filters, labels = [], [], []
    for i, it in enumerate(items):
        if it["narr"]:
            inputs += ["-i", it["narr"]]
            idx = len(inputs) // 2 - 1
            filters.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=mono,adelay={int(LEAD * 1000)}:all=1,"
                           f"apad=whole_dur={it['dur']},atrim=0:{it['dur']},asetpts=N/SR/TB[a{i}]")
        else:
            filters.append(f"anullsrc=r=48000:cl=mono,atrim=0:{it['dur']}[a{i}]")
        labels.append(f"[a{i}]")
    filters.append(f"{''.join(labels)}concat=n={len(items)}:v=0:a=1,apad=whole_dur={total},atrim=0:{total},"
                   "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]")
    ffmpeg(*inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-ac", 1, out)


def build_music(sb: dict, total: float, out: pathlib.Path, use_placeholder: bool) -> str:
    sel = sb["music"].get("selected")
    src = ROOT / sel if (sel and not use_placeholder and (ROOT / sel).exists()) else music.make_placeholder()
    fade_out = max(total - 4, 0)
    ffmpeg("-stream_loop", -1, "-i", src, "-af",
           f"atrim=0:{total},asetpts=N/SR/TB,afade=t=in:d=2,afade=t=out:st={fade_out}:d=4,"
           "loudnorm=I=-24:TP=-2:LRA=11,aresample=48000", "-ac", 2, out)
    return rel(src)


def loudnorm_two_pass(src: pathlib.Path, out: pathlib.Path, i=-14.0, tp=-1.0, lra=11.0) -> dict:
    log = ffmpeg("-i", src, "-af", f"loudnorm=I={i}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-", capture=True)
    m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
    ffmpeg("-i", src, "-af",
           f"loudnorm=I={i}:TP={tp}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
           f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
           "linear=true,aresample=48000", "-ar", 48000, out)
    return m


def mix(narr: pathlib.Path, mus: pathlib.Path, out: pathlib.Path) -> dict:
    raw = out.with_name("mix_raw.wav")
    fc = ("[0:a]pan=stereo|c0=c0|c1=c0,asplit=2[sc][voice];"
          "[1:a][sc]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[ducked];"
          "[ducked][voice]amix=inputs=2:normalize=0:duration=longest[m]")
    ffmpeg("-i", narr, "-i", mus, "-filter_complex", fc, "-map", "[m]", raw)
    return loudnorm_two_pass(raw, out)


# ---------------------------------------------------------------- video
def kenburns(camera: str, frames: int) -> tuple[str, str, str]:
    p = f"on/{frames}"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return {
        "push_in": (f"1+0.15*{p}", cx, cy),
        "pull_back": (f"1.15-0.15*{p}", cx, cy),
        "pan_left": ("1.12", f"(iw-iw/zoom)*(1-{p})", cy),
        "pan_right": ("1.12", f"(iw-iw/zoom)*{p}", cy),
        "tilt_up": ("1.12", cx, f"(ih-ih/zoom)*(1-{p})"),
        "tilt_down": ("1.12", cx, f"(ih-ih/zoom)*{p}"),
        "fixed": (f"1+0.04*{p}", cx, cy),
    }[camera]


def text_overlay(shot: dict, W: int, H: int, dur: float, tmp: pathlib.Path) -> str:
    ost = shot.get("on_screen_text")
    if not ost or not LATIN_FONT:
        return ""
    size = int(min(W, H) * 0.06)
    alpha = f"if(lt(t,0.6),t/0.6,if(gt(t,{dur - 0.8}),max(0,({dur}-t)/0.8),1))"
    common = f"fontcolor=white@0.95:borderw=3:bordercolor=black@0.35:x=(w-text_w)/2:alpha='{alpha}'"
    f_en = tmp / f"{shot['id']}_en.txt"
    f_en.write_text(ost["en"], encoding="utf-8")
    out = f",drawtext=fontfile='{LATIN_FONT}':textfile='{f_en}':fontsize={size}:y=h*0.12:{common}"
    if ost.get("am") and ETHIOPIC_FONT:
        f_am = tmp / f"{shot['id']}_am.txt"
        f_am.write_text(ost["am"], encoding="utf-8")
        out += f",drawtext=fontfile='{ETHIOPIC_FONT}':textfile='{f_am}':fontsize={int(size * 0.8)}:y=h*0.12+{int(size * 1.3)}:{common}"
    return out


def render_shot(sb: dict, it: dict, aspect: str, tmp: pathlib.Path) -> tuple[pathlib.Path, str]:
    s = it["shot"]
    W, H = ASPECTS[aspect]
    fps = sb["film"]["fps"]
    dur = it["dur"]
    frames = round(dur * fps)
    clip_key = shots.expected_key(sb, s)
    clip = Manifest("shots").valid(s["id"], clip_key) if clip_key else None
    kf = Manifest("keyframes").valid(s["id"], keyframes.expected_key(sb, s))
    if clip and s["motion"]["method"] == "i2v":
        mode, src = "clip", ROOT / clip["path"]
    elif kf:
        mode, src = "kenburns", ROOT / kf["path"]
    else:
        mode, src = "placeholder", None
    key = stable_hash({"v": 3, "mode": mode, "src": file_hash(src) if src else None, "dur": dur, "aspect": aspect,
                       "camera": s["motion"]["camera"], "text": s.get("on_screen_text"), "fps": fps,
                       "font": bool(ETHIOPIC_FONT)})
    out = EDIT / aspect / f"{s['id']}_{key[:10]}.mp4"
    if out.exists():
        return out, mode
    out.parent.mkdir(parents=True, exist_ok=True)
    overlay = text_overlay(s, W, H, dur, tmp)
    fit = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if mode == "clip":
        clip_len = max(probe_duration(src) - 0.25, 0.5)
        slow = min(max(dur / clip_len, 1.0), 1.6)          # gentle slow-down, then hold the last frame
        vf = (f"trim=start=0.25,setpts=(PTS-STARTPTS)*{slow:.4f},{fit},fps={fps},"
              f"tpad=stop_mode=clone:stop_duration={dur},trim=duration={dur},setpts=PTS-STARTPTS{overlay},format=yuv420p")
        inputs = ["-i", src]
    elif mode == "kenburns":
        z, x, y = kenburns(s["motion"]["camera"], frames)
        vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
              f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={fps}{overlay},format=yuv420p")
        inputs = ["-i", src]
    else:
        label = tmp / f"{s['id']}_ph.txt"
        label.write_text(f"{s['id']}  {s['beat']}", encoding="utf-8")
        vf = f"drawtext=fontfile='{LATIN_FONT}':textfile='{label}':fontsize={int(min(W, H) * 0.035)}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2,format=yuv420p"
        inputs = ["-f", "lavfi", "-i", f"color=c=0x2a1d14:s={W}x{H}:d={dur}:r={fps}"]
    ffmpeg(*inputs, "-vf", vf, "-frames:v", frames, "-r", fps, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", 18, "-pix_fmt", "yuv420p", "-an", out)
    return out, mode


def render_endcard(sb: dict, aspect: str, tmp: pathlib.Path) -> pathlib.Path:
    W, H = ASPECTS[aspect]
    ec = sb["film"]["end_card"]
    fps = sb["film"]["fps"]
    out = EDIT / aspect / f"endcard_{stable_hash([ec, aspect])[:10]}.mp4"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    sizes = {"large": 0.065, "medium": 0.05, "small": 0.03}
    hs = [int(min(W, H) * sizes[line["size"]]) for line in ec["lines"]]
    gap = int(min(W, H) * 0.03)
    y = (H - (sum(hs) + gap * (len(hs) - 1))) // 2
    draws = []
    for i, (line, h) in enumerate(zip(ec["lines"], hs)):
        f = tmp / f"end_{i}.txt"
        f.write_text(line["text"], encoding="utf-8")
        color = "0xF3E6D3" if line["size"] != "small" else "0xC9B79F"
        draws.append(f"drawtext=fontfile='{LATIN_FONT}':textfile='{f}':fontsize={h}:fontcolor={color}:x=(w-text_w)/2:y={y}")
        y += h + gap
    vf = ",".join(draws) + ",fade=t=in:st=0:d=0.6,format=yuv420p"
    ffmpeg("-f", "lavfi", "-i", f"color=c=0x1b120c:s={W}x{H}:d={ec['duration_s']}:r={fps}", "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", 18, "-pix_fmt", "yuv420p", "-an", out)
    return out


def final_mux(video: pathlib.Path, audio: pathlib.Path, srt: pathlib.Path, style: str, out: pathlib.Path, fps: int) -> None:
    vf = f"subtitles=filename='{srt}':force_style='{style}',format=yuv420p"
    ffmpeg("-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-vf", vf, "-r", fps,
           "-c:v", "libx264", "-preset", "medium", "-crf", 20, "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", 48000, "-movflags", "+faststart", "-shortest", out)


# ---------------------------------------------------------------- entry points
def build_audio(sb, items, total, work, placeholder) -> tuple[pathlib.Path, dict, str]:
    narr, mus, final = work / "narration.wav", work / "music.wav", work / "mix.wav"
    build_narration(items, total, narr)
    src = build_music(sb, total, mus, placeholder)
    meas = mix(narr, mus, final)
    return final, meas, src


def radio_cut() -> None:
    sb = load_storyboard()
    items, total = timeline(sb)
    missing = [it["shot"]["id"] for it in items if not it["narr"]]
    FILM.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        audio, meas, src = build_audio(sb, items, total, work, placeholder=True)
        srt = work / "radio.srt"
        write_srt(items, srt)
        black = work / "black.mp4"
        ffmpeg("-f", "lavfi", "-i", f"color=c=black:s=1280x720:d={total}:r=24", "-c:v", "libx264", "-pix_fmt", "yuv420p", black)
        out = FILM / "radio_cut.mp4"
        final_mux(black, audio, srt, SUB["radio"], out, 24)
        ffmpeg("-i", audio, "-c:a", "libmp3lame", "-b:a", "160k", FILM / "radio_cut.mp3")
    print(f"radio cut: {rel(out)}  ({total:.1f}s, input loudness {meas['input_i']} LUFS)")
    if missing:
        print(f"  no narration yet for: {', '.join(missing)}")


def film(aspects: list[str]) -> None:
    sb = load_storyboard()
    items, shots_total = timeline(sb)
    total = round(shots_total + sb["film"]["end_card"]["duration_s"], 3)
    fps = sb["film"]["fps"]
    FILM.mkdir(parents=True, exist_ok=True)
    report = {"duration_s": total, "shots": []}
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        audio, meas, src = build_audio(sb, items, total, work, placeholder=False)
        report.update(music_source=src, loudness_in=meas)
        srt = FILM / "subtitles_en.srt"
        write_srt(items, srt)
        for aspect in aspects:
            parts, modes = [], {}
            for it in items:
                p, mode = render_shot(sb, it, aspect, work)
                parts.append(p)
                modes[it["shot"]["id"]] = mode
            parts.append(render_endcard(sb, aspect, work))
            lst = work / f"concat_{aspect}.txt"
            lst.write_text("".join(f"file '{p}'\n" for p in parts))
            video = work / f"video_{aspect}.mp4"
            ffmpeg("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", video)
            out = FILM / f"buna_{aspect}.mp4"
            final_mux(video, audio, srt, SUB[aspect], out, fps)
            print(f"{rel(out)}  {probe_duration(out):.1f}s  " + " ".join(f"{k}:{v}" for k, v in modes.items()))
            report["shots"] = [{"id": it["shot"]["id"], "start": it["start"], "dur": it["dur"], "mode": modes[it["shot"]["id"]]} for it in items]
    (FILM / "edit_report.json").write_text(json.dumps(report, indent=2))
    if not 60 <= total <= 90:
        print(f"WARNING: film is {total:.1f}s, outside 60-90s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radio", action="store_true")
    ap.add_argument("--aspect", choices=[*ASPECTS, "both"], default="both")
    a = ap.parse_args()
    t0 = time.time()
    if a.radio:
        radio_cut()
    else:
        film(list(ASPECTS) if a.aspect == "both" else [a.aspect])
    print(f"assembly done in {time.time() - t0:.1f}s")
