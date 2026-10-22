"""The editing step: out/cuts.json + out/raw/*.webm -> out/compass-demo.mp4 (and the clean cut).

Per scene: the useful segments of each context's raw video are trimmed and joined (the model
waits are cut out), sped up when they run over the scene's target, and put on a 1920x1080 navy
frame (one clip centred, or two side by side for the split-screen scenes 5 and 9). The captions
are PNG overlays rendered by captions.mjs (ffmpeg's drawtext breaks Hebrew bidi order). Scenes
join with a 0.25 s crossfade. Silent. H.264, yuv420p, +faststart, 30 fps; the file is asserted
to be at most 60.0 s and 50 MB.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
WORK = OUT / "work"
CAPTIONS = OUT / "captions"
FRAMES = OUT / "frames"

FPS = 30
FADE = 0.25
NAVY = "0x082350"
MAX_SECONDS = 60.0
MAX_BYTES = 50 * 1024 * 1024
MIN_SCENE = 2.5
MAX_SPEEDUP = 3.0
CLOSE_SECONDS = 3.0
# the storyboard's target seconds per scene (the brief's table); a longer scene is sped up to fit
TARGETS = {0: 3, 1: 2, 2: 7, 3: 4, 4: 5, 5: 8, 6: 6, 7: 5, 8: 6, 9: 8, 10: 3}
SPLIT_SCENES = {5, 9}  # two panes, side by side


def find_tool(name: str, required: bool = True) -> str | None:
    """PATH first, then winget's Gyan.FFmpeg, then the imageio-ffmpeg binary vendored under
    tools/video/.vendor (ffmpeg only; it ships no ffprobe)."""
    found = shutil.which(name)
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA", "")
    pattern = os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", f"{name}.exe")
    hits = sorted(glob.glob(pattern, recursive=True))
    if hits:
        return hits[0]
    if name == "ffmpeg":
        vendor = str(HERE / ".vendor")
        if vendor not in sys.path:
            sys.path.insert(0, vendor)
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
    if not required:
        return None
    sys.exit(
        f"record-video: {name} was not found. Install it with `winget install Gyan.FFmpeg`, "
        "then open a NEW terminal (the PATH changes only for new ones) and run this again."
    )


def run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(result.stderr[-1500:], file=sys.stderr)
        sys.exit(f"record-video: ffmpeg failed ({Path(args[0]).stem})")


def duration_of(path: Path) -> float:
    probe = find_tool("ffprobe", required=False)
    if probe is None:  # no ffprobe: read "Duration: hh:mm:ss.xx" from `ffmpeg -i`
        text = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
        found = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", text)
        if found is None:
            sys.exit(f"record-video: cannot read the duration of {path.name}")
        h, m, s = found.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    out = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return float(out.strip())


def pane_filters(ffmpeg_inputs: list[str], first_input: int, segments: list[dict], raw: dict, label: str) -> tuple[list[str], float]:
    """The trimmed, joined segments of one pane as `[label]`; returns (filters, seconds)."""
    filters, names, total = [], [], 0.0
    for j, seg in enumerate(segments):
        index = first_input + j
        ffmpeg_inputs += ["-i", str(HERE / raw[seg["ctx"]])]
        start, end = float(seg["start"]), float(seg["end"])
        name = f"{label}s{j}"
        filters.append(
            f"[{index}:v]setpts=PTS-STARTPTS,fps={FPS},trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,scale=1440:900,setsar=1[{name}]"
        )
        names.append(f"[{name}]")
        total += end - start
    filters.append(f"{''.join(names)}concat=n={len(names)}:v=1:a=0[{label}]")
    return filters, total


def render_scene(n: int, panes: list[list[dict]], raw: dict) -> Path:
    """One scene -> work/clean/scene-NN.mp4 (1920x1080, navy, no captions)."""
    ffmpeg = find_tool("ffmpeg")
    target = TARGETS[n]
    panes = [p for p in panes if p]
    inputs: list[str] = []
    filters: list[str] = []
    lengths: list[float] = []
    cursor = 0
    for p, segs in enumerate(panes):
        f, total = pane_filters(inputs, cursor, segs, raw, f"p{p}")
        filters += f
        lengths.append(total)
        cursor += len(segs)
    longest = max(lengths)
    speed = min(max(longest / target, 1.0), MAX_SPEEDUP)
    final = max(longest / speed, MIN_SCENE)
    labels = []
    for p, total in enumerate(lengths):
        have = total / speed
        pad = f",tpad=stop_mode=clone:stop_duration={max(final - have, 0):.3f}" if final - have > 0.01 else ""
        width, height = (960, 600) if n in SPLIT_SCENES else (1728, 1080)
        filters.append(f"[p{p}]setpts=PTS/{speed:.4f}{pad},scale={width}:{height}:flags=lanczos,setsar=1[q{p}]")
        labels.append(f"[q{p}]")
    if len(labels) == 2:
        filters.append(f"{''.join(labels)}hstack=inputs=2,pad=1920:1080:0:(oh-ih)/2:color={NAVY}[v]")
    else:
        filters.append(f"{labels[0]}pad=1920:1080:(ow-iw)/2:0:color={NAVY}[v]")
    target_file = WORK / "clean" / f"scene-{n:02d}.mp4"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", "[v]", "-t", f"{final:.3f}",
         "-r", str(FPS), "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", str(target_file)])
    return target_file


def render_close() -> Path:
    target_file = WORK / "clean" / "scene-10.mp4"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    run([find_tool("ffmpeg"), "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-t", str(CLOSE_SECONDS),
         "-i", str(CAPTIONS / "close.png"), "-vf", f"scale=1920:1080,format=yuv420p", "-r", str(FPS), "-an",
         "-c:v", "libx264", "-preset", "fast", "-crf", "14", str(target_file)])
    return target_file


def caption_scene(n: int, clean: Path) -> Path:
    """The same scene with its caption (and scene 0's honesty line) faded in and out."""
    seconds = duration_of(clean)
    overlays = [(CAPTIONS / f"scene-{n:02d}.png", 130 if n == 0 else 90)]
    note = CAPTIONS / f"scene-{n:02d}-note.png"
    if note.exists():
        overlays.append((note, 52))
    inputs = ["-i", str(clean)]
    chains, last = [], "[0:v]"
    for i, (png, from_bottom) in enumerate(overlays, start=1):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", str(png)]
        chains.append(
            f"[{i}:v]format=rgba,fade=t=in:st=0.2:d=0.3:alpha=1,fade=t=out:st={max(seconds - 0.55, 0.3):.3f}:d=0.3:alpha=1[c{i}]"
        )
        chains.append(f"{last}[c{i}]overlay=x=(W-w)/2:y=H-h-{from_bottom}:shortest=1[o{i}]")
        last = f"[o{i}]"
    target_file = WORK / "captioned" / f"scene-{n:02d}.mp4"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    run([find_tool("ffmpeg"), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chains), "-map", last, "-r", str(FPS),
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", str(target_file)])
    return target_file


def join(files: list[Path], target: Path) -> tuple[float, int]:
    """Crossfade the scenes (0.25 s) and encode; the CRF rises until the file fits 50 MB."""
    ffmpeg = find_tool("ffmpeg")
    inputs: list[str] = []
    for f in files:
        inputs += ["-i", str(f)]
    lengths = [duration_of(f) for f in files]
    filters, current, length = [], "[0:v]", lengths[0]
    for i in range(1, len(files)):
        offset = length - FADE
        out = f"[x{i}]"
        filters.append(f"{current}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}{out}")
        current, length = out, length + lengths[i] - FADE
    for crf in (23, 26, 29, 32, 35):
        run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", current, "-r", str(FPS),
             "-an", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(target)])
        if target.stat().st_size <= MAX_BYTES:
            break
    return duration_of(target), target.stat().st_size


def main() -> int:
    find_tool("ffmpeg")
    cuts = json.loads((OUT / "cuts.json").read_text(encoding="utf-8"))
    raw = cuts["rawFiles"]
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(FRAMES, ignore_errors=True)
    FRAMES.mkdir(parents=True, exist_ok=True)

    node = shutil.which("node")
    if node is None:
        sys.exit("record-video: node is not on PATH")
    subprocess.run([node, str(HERE / "captions.mjs")], check=True)

    scenes = {s["n"]: s["panes"] for s in cuts["scenes"]}
    clean: list[Path] = []
    captioned: list[Path] = []
    rows = []
    for n in range(0, 11):
        clean_file = render_close() if n == 10 else render_scene(n, scenes[n], raw)
        clean.append(clean_file)
        captioned_file = caption_scene(n, clean_file)
        captioned.append(captioned_file)
        seconds = duration_of(captioned_file)
        useful = 0.0 if n == 10 else max(sum(float(x["end"]) - float(x["start"]) for x in p) for p in scenes[n] if p)
        rows.append({"scene": n, "target_s": TARGETS[n], "useful_cut_s": round(useful, 2), "in_video_s": round(seconds, 2)})
        key = max(min(seconds - 0.8, seconds * 0.8), 0.5)
        run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{key:.2f}", "-i", str(captioned_file), "-frames:v", "1",
             str(FRAMES / f"scene-{n:02d}.png")])

    seconds, size = join(captioned, OUT / "compass-demo.mp4")
    clean_seconds, clean_size = join(clean, OUT / "compass-demo-clean.mp4")
    (OUT / "timings.json").write_text(json.dumps({"scenes": rows, "seconds": seconds, "bytes": size}, indent=2), encoding="utf-8")
    shutil.rmtree(WORK, ignore_errors=True)

    print("\nscene  target  useful-cut  in-video")
    for r in rows:
        print(f"{r['scene']:>5}  {r['target_s']:>5}s  {r['useful_cut_s']:>9}s  {r['in_video_s']:>7}s")
    print(f"\ncompass-demo.mp4        {seconds:.1f} s   {size / 1048576:.1f} MB")
    print(f"compass-demo-clean.mp4  {clean_seconds:.1f} s   {clean_size / 1048576:.1f} MB")
    problems = []
    for name, sec, byte in (("compass-demo.mp4", seconds, size), ("compass-demo-clean.mp4", clean_seconds, clean_size)):
        if sec > MAX_SECONDS:
            problems.append(f"{name} is {sec:.1f} s, over {MAX_SECONDS:.0f} s")
        if byte > MAX_BYTES:
            problems.append(f"{name} is {byte / 1048576:.1f} MB, over 50 MB")
    if problems:
        print("FAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    print("OK: duration and size are within the limits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
