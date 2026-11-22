"""Video ops. One op = one entry in OPS plus one small builder below.

Every op turns into ffmpeg filters, so the whole edit runs in one ffmpeg
call. No GUI, no account, just ffmpeg doing the work.
"""

import json
import math
import subprocess

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


class Ctx:
    """Everything builders collect while walking the ops list."""

    def __init__(self):
        self.vf = []
        self.af = []
        self.start = None
        self.duration = None
        self.crf = None
        self.mode = "video"  # video | audio | frame | gif
        self.audio_format = None
        self.frame_time = 0.0
        self.gif = {}
        self.mute = False


def _num(op, params, key, default=None, lo=None, hi=None):
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


def _int(op, params, key, default=None, lo=None, hi=None):
    v = _num(op, params, key, default, lo, hi)
    if v != int(v):
        raise ValueError(f"'{op}': '{key}' has to be a whole number")
    return int(v)


def _atempo_chain(factor):
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


def _trim(ctx, p):
    start = _num("trim", p, "start", 0, lo=0)
    end = p.get("end")
    dur = p.get("duration")
    if end is not None and dur is not None:
        raise ValueError("'trim': give 'end' or 'duration', not both")
    if end is not None:
        end = _num("trim", p, "end", lo=0)
        if end <= start:
            raise ValueError("'trim': 'end' has to be after 'start'")
        ctx.duration = end - start
    elif dur is not None:
        ctx.duration = _num("trim", p, "duration", lo=0.01)
    ctx.start = start


def _speed(ctx, p):
    f = _num("speed", p, "factor", lo=0.25, hi=4)
    ctx.vf.append(f"setpts={1 / f:.4f}*PTS")
    ctx.af.extend(_atempo_chain(f))


def _scale(ctx, p):
    w = p.get("width", -1)
    h = p.get("height", -1)
    if w == -1 and h == -1:
        raise ValueError("'scale': give width, height, or both")
    ctx.vf.append(f"scale={int(w)}:{int(h)}")


def _crop(ctx, p):
    w = _int("crop", p, "width", lo=2)
    h = _int("crop", p, "height", lo=2)
    x = _int("crop", p, "x", 0, lo=0)
    y = _int("crop", p, "y", 0, lo=0)
    ctx.vf.append(f"crop={w}:{h}:{x}:{y}")


def _rotate(ctx, p):
    deg = p.get("degrees", 90)
    if deg == 90:
        ctx.vf.append("transpose=1")
    elif deg == 180:
        ctx.vf.append("hflip,vflip")
    elif deg == 270:
        ctx.vf.append("transpose=2")
    else:
        raise ValueError("'rotate': degrees has to be 90, 180 or 270")


def _flip_h(ctx, p):
    ctx.vf.append("hflip")


def _flip_v(ctx, p):
    ctx.vf.append("vflip")


def _fps(ctx, p):
    ctx.vf.append(f"fps={_int('fps', p, 'fps', lo=1, hi=120)}")


def _brightness(ctx, p):
    ctx.vf.append(f"eq=brightness={_num('brightness', p, 'value', lo=-1, hi=1):.3f}")


def _contrast(ctx, p):
    ctx.vf.append(f"eq=contrast={_num('contrast', p, 'value', lo=0.1, hi=3):.3f}")


def _saturation(ctx, p):
    ctx.vf.append(f"eq=saturation={_num('saturation', p, 'factor', lo=0, hi=3):.3f}")


def _gamma(ctx, p):
    ctx.vf.append(f"eq=gamma={_num('gamma', p, 'value', lo=0.1, hi=3):.3f}")


def _hue(ctx, p):
    ctx.vf.append(f"hue=h={_num('hue', p, 'degrees', lo=-180, hi=180):.1f}")


def _grayscale(ctx, p):
    ctx.vf.append("hue=s=0")


def _blur(ctx, p):
    ctx.vf.append(f"gblur=sigma={_num('blur', p, 'radius', lo=0.5, hi=20):.2f}")


def _sharpen(ctx, p):
    ctx.vf.append(f"unsharp=5:5:{_num('sharpen', p, 'strength', lo=0, hi=5):.2f}")


def _vignette(ctx, p):
    s = _num("vignette", p, "strength", lo=0, hi=1)
    angle = math.pi - s * (math.pi * 0.8)
    ctx.vf.append(f"vignette=angle={angle:.3f}")


def _denoise(ctx, p):
    ctx.vf.append("hqdn3d")


def _reverse(ctx, p):
    # play it backwards, picture and sound together
    ctx.vf.append("reverse")
    ctx.af.append("areverse")


def _invert(ctx, p):
    # negative video, colours flipped; audio untouched
    ctx.vf.append("negate")


def _volume(ctx, p):
    ctx.af.append(f"volume={_num('volume', p, 'factor', lo=0, hi=5):.3f}")


def _mute(ctx, p):
    ctx.mute = True


def _fade_in(ctx, p):
    d = _num("fade_in", p, "duration", lo=0.1, hi=30)
    ctx.vf.append(f"fade=t=in:st=0:d={d:.2f}")
    ctx.af.append(f"afade=t=in:st=0:d={d:.2f}")


def _fade_out(ctx, p):
    d = _num("fade_out", p, "duration", lo=0.1, hi=30)
    ctx.vf.append(f"fade=t=out:st=0:d={d:.2f}")
    ctx.af.append(f"afade=t=out:st=0:d={d:.2f}")


def _text(ctx, p):
    text = p.get("text")
    if not text:
        raise ValueError("'text': give some 'text' to draw")
    safe = str(text).replace("'", "").replace(":", "\\:").replace("%", "\\%")
    x = p.get("x", "(w-text_w)/2")
    y = p.get("y", "h-text_h-20")
    size = _int("text", p, "fontsize", 32, lo=8, hi=200)
    ctx.vf.append(
        f"drawtext=fontfile={FONT}:text='{safe}':x={x}:y={y}:fontsize={size}:fontcolor=white:borderw=2:bordercolor=black"
    )


def _extract_audio(ctx, p):
    fmt = p.get("format", "mp3")
    if fmt not in ("mp3", "wav", "aac", "ogg"):
        raise ValueError("'extract_audio': format has to be mp3, wav, aac or ogg")
    ctx.mode = "audio"
    ctx.audio_format = fmt


def _thumbnail(ctx, p):
    ctx.mode = "frame"
    ctx.frame_time = _num("thumbnail", p, "time", 1, lo=0)
    w = p.get("width")
    if w:
        ctx.vf.append(f"scale={_int('thumbnail', p, 'width', lo=16)}:-1")


def _gif(ctx, p):
    ctx.mode = "gif"
    ctx.gif = {
        "start": _num("gif", p, "start", 0, lo=0),
        "duration": _num("gif", p, "duration", 2, lo=0.5, hi=30),
        "fps": _int("gif", p, "fps", 10, lo=1, hi=30),
        "width": _int("gif", p, "width", 320, lo=16, hi=1920),
    }


def _compress(ctx, p):
    ctx.crf = _int("compress", p, "crf", 23, lo=18, hi=32)


OPS = {
    "trim": {"description": "Keep only start..end (seconds).", "params": {"start": {"type": "number", "default": 0, "min": 0}, "end": {"type": "number", "min": 0}, "duration": {"type": "number", "min": 0.01}}, "build": _trim},
    "speed": {"description": "Play faster or slower, video and audio together.", "params": {"factor": {"type": "number", "default": 1, "min": 0.25, "max": 4}}, "build": _speed},
    "scale": {"description": "Resize. Use -1 on one side to keep the aspect ratio.", "params": {"width": {"type": "integer", "default": -1}, "height": {"type": "integer", "default": -1}}, "build": _scale},
    "crop": {"description": "Cut a rectangle out of the frame.", "params": {"width": {"type": "integer", "min": 2}, "height": {"type": "integer", "min": 2}, "x": {"type": "integer", "default": 0, "min": 0}, "y": {"type": "integer", "default": 0, "min": 0}}, "build": _crop},
    "rotate": {"description": "Rotate the frame.", "params": {"degrees": {"type": "integer", "enum": [90, 180, 270], "default": 90}}, "build": _rotate},
    "flip_h": {"description": "Mirror left-right.", "params": {}, "build": _flip_h},
    "flip_v": {"description": "Flip top-bottom.", "params": {}, "build": _flip_v},
    "fps": {"description": "Change the frame rate.", "params": {"fps": {"type": "integer", "min": 1, "max": 120}}, "build": _fps},
    "brightness": {"description": "Lighten or darken, -1 to 1.", "params": {"value": {"type": "number", "min": -1, "max": 1}}, "build": _brightness},
    "contrast": {"description": "Contrast, 0.1 to 3.", "params": {"value": {"type": "number", "min": 0.1, "max": 3}}, "build": _contrast},
    "saturation": {"description": "Colour intensity, 0 is grey, 1 is normal.", "params": {"factor": {"type": "number", "min": 0, "max": 3}}, "build": _saturation},
    "gamma": {"description": "Midtone brightness, 0.1 to 3.", "params": {"value": {"type": "number", "min": 0.1, "max": 3}}, "build": _gamma},
    "hue": {"description": "Shift colours, -180 to 180 degrees.", "params": {"degrees": {"type": "number", "min": -180, "max": 180}}, "build": _hue},
    "grayscale": {"description": "Black and white.", "params": {}, "build": _grayscale},
    "blur": {"description": "Soften the frame.", "params": {"radius": {"type": "number", "min": 0.5, "max": 20}}, "build": _blur},
    "sharpen": {"description": "Crisp edges, 0 to 5.", "params": {"strength": {"type": "number", "min": 0, "max": 5}}, "build": _sharpen},
    "vignette": {"description": "Darken the corners, 0 to 1.", "params": {"strength": {"type": "number", "min": 0, "max": 1}}, "build": _vignette},
    "denoise": {"description": "Clean up grain and noise.", "params": {}, "build": _denoise},
    "reverse": {"description": "Play the clip backwards, video and audio.", "params": {}, "build": _reverse},
    "invert": {"description": "Negative video, colours flipped. Audio untouched.", "params": {}, "build": _invert},
    "volume": {"description": "Audio volume, 0 to 5.", "params": {"factor": {"type": "number", "min": 0, "max": 5}}, "build": _volume},
    "mute": {"description": "Drop the audio track.", "params": {}, "build": _mute},
    "fade_in": {"description": "Fade in from black, video and audio.", "params": {"duration": {"type": "number", "min": 0.1, "max": 30}}, "build": _fade_in},
    "fade_out": {"description": "Fade out to black, video and audio.", "params": {"duration": {"type": "number", "min": 0.1, "max": 30}}, "build": _fade_out},
    "text": {"description": "Draw text on the video.", "params": {"text": {"type": "string"}, "x": {"type": "string", "default": "(w-text_w)/2"}, "y": {"type": "string", "default": "h-text_h-20"}, "fontsize": {"type": "integer", "default": 32, "min": 8, "max": 200}}, "build": _text},
    "extract_audio": {"description": "Save just the audio as mp3, wav, aac or ogg.", "params": {"format": {"type": "string", "enum": ["mp3", "wav", "aac", "ogg"], "default": "mp3"}}, "build": _extract_audio},
    "thumbnail": {"description": "Grab one frame as an image.", "params": {"time": {"type": "number", "default": 1, "min": 0}, "width": {"type": "integer", "min": 16}}, "build": _thumbnail},
    "gif": {"description": "Make a small looping gif from a clip.", "params": {"start": {"type": "number", "default": 0, "min": 0}, "duration": {"type": "number", "default": 2, "min": 0.5, "max": 30}, "fps": {"type": "integer", "default": 10, "min": 1, "max": 30}, "width": {"type": "integer", "default": 320, "min": 16, "max": 1920}}, "build": _gif},
    "compress": {"description": "Smaller file, same video. Lower crf = better quality.", "params": {"crf": {"type": "integer", "default": 23, "min": 18, "max": 32}}, "build": _compress},
}


def list_ops():
    return {name: {"description": spec["description"], "params": spec["params"]} for name, spec in OPS.items()}


def build_ctx(ops):
    if not isinstance(ops, list) or not ops:
        raise ValueError("ops has to be a non-empty list, e.g. [{\"op\": \"trim\", \"start\": 2}]")
    ctx = Ctx()
    applied = []
    for item in ops:
        if not isinstance(item, dict) or "op" not in item:
            raise ValueError("every op needs an 'op' name, e.g. {\"op\": \"trim\", \"start\": 2}")
        name = item["op"]
        if name not in OPS:
            raise ValueError(f"unknown op '{name}'. Run 'vidforge ops' to see them all.")
        OPS[name]["build"](ctx, item)
        applied.append(name)
    return ctx, applied


def probe(path):
    """ffprobe as a dict: duration, size, fps, codecs, has_audio."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", path],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise ValueError(f"can't read '{path}': {e}")
    data = json.loads(out.stdout)
    info = {"duration": None, "width": None, "height": None, "fps": None, "has_audio": False}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["width"] is None:
            info.update({"width": s.get("width"), "height": s.get("height"), "video_codec": s.get("codec_name")})
            rate = s.get("avg_frame_rate", "0/1").split("/")
            if len(rate) == 2 and int(rate[1]):
                info["fps"] = round(int(rate[0]) / int(rate[1]), 2)
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
            info["audio_codec"] = s.get("codec_name")
    fmt = data.get("format", {})
    if fmt.get("duration"):
        info["duration"] = round(float(fmt["duration"]), 2)
    return info
