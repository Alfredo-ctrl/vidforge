"""ffmpeg plumbing shared by vidforge and audforge.

Same file in both repos, kept in sync by hand, so each repo still installs
on its own. If this ever grows past ffmpeg helpers, it should become a real
shared package instead of a copy.
"""

import json
import os
import subprocess
import tempfile

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def num(op, params, key, default=None, lo=None, hi=None):
    v = params.get(key, default)
    if v is None:
        raise ValueError(f"'{op}' needs '{key}'")
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"'{op}': '{key}' has to be a number, got {params.get(key)!r}")
    if lo is not None and v < lo:
        raise ValueError(f"'{op}': '{key}' can't be under {lo}")
    if hi is not None and v > hi:
        raise ValueError(f"'{op}': '{key}' can't be over {hi}")
    return v


def whole(op, params, key, default=None, lo=None, hi=None):
    v = num(op, params, key, default, lo, hi)
    if v != int(v):
        raise ValueError(f"'{op}': '{key}' has to be a whole number")
    return int(v)


def atempo_chain(factor):
    # atempo only takes 0.5-2.0, so chain it for bigger changes
    parts = []
    f = factor
    while f > 2.0:
        parts.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        parts.append("atempo=0.5")
        f /= 0.5
    parts.append(f"atempo={f:.4f}")
    return parts


def trim(ctx, p):
    start = num("trim", p, "start", 0, lo=0)
    end = p.get("end")
    dur = p.get("duration")
    if end is not None and dur is not None:
        raise ValueError("'trim': give 'end' or 'duration', not both")
    if end is not None:
        end = num("trim", p, "end", lo=0)
        if end <= start:
            raise ValueError("'trim': 'end' has to be after 'start'")
        ctx.duration = end - start
    elif dur is not None:
        ctx.duration = num("trim", p, "duration", lo=0.01)
    ctx.start = start


def fade_out_at(kind, duration, total):
    """fade/afade filter that starts `duration` before the end of the clip."""
    start = max(total - duration, 0)
    if kind == "video":
        return f"fade=t=out:st={start:.2f}:d={duration:.2f}"
    return f"afade=t=out:st={start:.2f}:d={duration:.2f}"


def concat_list(paths):
    """Write an ffmpeg concat list to a unique temp file. Caller deletes it."""
    fd, path = tempfile.mkstemp(prefix="forge-join-", suffix=".txt")
    with os.fdopen(fd, "w") as f:
        for p in paths:
            f.write(f"file '{p.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n")
    return path


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = (res.stderr or "").strip().splitlines()
        tail = " ".join(err[-3:]) if err else "ffmpeg failed"
        raise RuntimeError(f"ffmpeg failed: {tail[:500]}")
    return res


def probe_raw(path):
    """ffprobe output as a dict, or ValueError if the file can't be read."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", path],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise ValueError(f"can't read '{path}': {e}")
    return json.loads(out.stdout)
