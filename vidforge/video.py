"""Run ffmpeg. One call per edit, JSON-friendly errors."""

import json
import subprocess

from .ops import FFMPEG, build_ctx, probe

_AUDIO_CODEC = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac", "ogg": "libvorbis"}


def _run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = (res.stderr or "").strip().splitlines()
        tail = " ".join(err[-3:]) if err else "ffmpeg failed"
        raise RuntimeError(f"ffmpeg failed: {tail[:500]}")
    return res


def apply_ops(input_path, output_path, ops):
    ctx, applied = build_ctx(ops)
    info_in = probe(input_path)

    # fade_out needs the real end time, so pin it to the clip length
    if "fade_out" in applied:
        total = ctx.duration if ctx.duration is not None else info_in["duration"]
        if ctx.loops:
            total = total * ctx.loops
        start = ctx.start or 0
        for i, f in enumerate(ctx.vf):
            if f.startswith("fade=t=out:"):
                d = float(f.split("d=")[1])
                ctx.vf[i] = f"fade=t=out:st={max(total - d, 0):.2f}:d={d:.2f}"
        for i, f in enumerate(ctx.af):
            if f.startswith("afade=t=out:"):
                d = float(f.split("d=")[1])
                ctx.af[i] = f"afade=t=out:st={max(total - d, 0):.2f}:d={d:.2f}"

    cmd = [FFMPEG, "-y", "-v", "error"]
    if ctx.start is not None:
        cmd += ["-ss", str(ctx.start)]
    if ctx.duration is not None and ctx.mode == "video":
        cmd += ["-t", str(ctx.duration)]
    if ctx.loops:
        cmd += ["-stream_loop", str(ctx.loops - 1)]
    cmd += ["-i", input_path]

    if ctx.mode == "audio":
        cmd += ["-vn", "-c:a", _AUDIO_CODEC[ctx.audio_format]]
    elif ctx.mode == "frame":
        cmd += ["-ss", str(ctx.frame_time), "-frames:v", "1"]
        if ctx.vf:
            cmd += ["-vf", ",".join(ctx.vf)]
    elif ctx.mode == "gif":
        g = ctx.gif
        base = list(ctx.vf) + [f"fps={g['fps']}", f"scale={g['width']}:-1:flags=lanczos"]
        filt = ",".join(base) + ",split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse"
        cmd = [FFMPEG, "-y", "-v", "error", "-ss", str(g["start"]), "-t", str(g["duration"]),
               "-i", input_path, "-filter_complex", filt, "-loop", "0"]
    else:
        if ctx.vf:
            cmd += ["-vf", ",".join(ctx.vf)]
        if ctx.mute or not info_in["has_audio"]:
            cmd += ["-an"]
        elif ctx.af:
            cmd += ["-af", ",".join(ctx.af)]
        cmd += ["-c:v", "libx264", "-preset", "fast"]
        if ctx.crf is not None:
            cmd += ["-crf", str(ctx.crf)]
        if info_in["has_audio"]:
            cmd += ["-c:a", "aac"]

    cmd.append(output_path)
    _run(cmd)

    out = {"output": output_path, "ops_applied": applied}
    if ctx.mode in ("video", "gif"):
        out.update(probe(output_path))
    elif ctx.mode == "audio":
        out.update({"duration": probe(output_path).get("duration"), "format": ctx.audio_format})
    else:
        out.update(probe(output_path))
    return out


def join_videos(inputs, output_path):
    """Stick clips together, in order. Re-encodes so mixed files still join."""
    if len(inputs) < 2:
        raise ValueError("join needs at least 2 videos")
    for p in inputs:
        probe(p)
    with open("/tmp/vidforge-join.txt", "w") as f:
        for p in inputs:
            f.write(f"file '{p}'\n")
    _run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", "/tmp/vidforge-join.txt", "-c:v", "libx264", "-preset", "fast",
          "-c:a", "aac", output_path])
    return {"output": output_path, "inputs": inputs, **probe(output_path)}


def describe(path):
    return probe(path)
