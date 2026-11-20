"""Short vertical clip for socials: trim, crop, caption, fade out."""

from vidforge import apply_ops

out = apply_ops("clip.mp4", "clip-vertical.mp4", [
    {"op": "trim", "start": 2, "end": 12},
    {"op": "crop", "width": 720, "height": 1280, "x": 280, "y": 0},
    {"op": "text", "text": "mira esto", "y": "h-text_h-80", "fontsize": 48},
    {"op": "fade_out", "duration": 1},
])
print(out)
