"""Tests run against a small generated clip, no fixtures needed."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vidforge import apply_ops, describe, join_videos, list_ops  # noqa: E402


def _make_clip(path, duration=4):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=30:duration={duration}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", path],
        check=True,
    )


class TestVidforge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.clip = os.path.join(cls.tmp, "clip.mp4")
        _make_clip(cls.clip)

    def out(self, name):
        return os.path.join(self.tmp, name)

    def test_ops_list(self):
        ops = list_ops()
        self.assertGreaterEqual(len(ops), 24)
        self.assertIn("trim", ops)
        self.assertIn("gif", ops)

    def test_describe(self):
        info = describe(self.clip)
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertAlmostEqual(info["duration"], 4, delta=0.3)
        self.assertTrue(info["has_audio"])

    def test_trim_and_scale(self):
        out = apply_ops(self.clip, self.out("t.mp4"),
                         [{"op": "trim", "start": 1, "end": 3},
                          {"op": "scale", "width": 160, "height": -1}])
        self.assertAlmostEqual(out["duration"], 2, delta=0.3)
        self.assertEqual(out["width"], 160)

    def test_speed(self):
        out = apply_ops(self.clip, self.out("s.mp4"), [{"op": "speed", "factor": 2}])
        self.assertAlmostEqual(out["duration"], 2, delta=0.3)

    def test_look_ops(self):
        out = apply_ops(self.clip, self.out("look.mp4"),
                        [{"op": "grayscale"}, {"op": "brightness", "value": 0.1},
                         {"op": "contrast", "value": 1.2}, {"op": "blur", "radius": 1},
                         {"op": "sharpen", "strength": 1}, {"op": "vignette", "strength": 0.5},
                         {"op": "denoise"}, {"op": "hue", "degrees": 20},
                         {"op": "saturation", "factor": 1.1}, {"op": "gamma", "value": 1.1}])
        self.assertEqual(out["ops_applied"][0], "grayscale")
        self.assertTrue(os.path.getsize(self.out("look.mp4")) > 1000)

    def test_rotate_crop_flip_fps(self):
        out = apply_ops(self.clip, self.out("r.mp4"),
                        [{"op": "rotate", "degrees": 90},
                         {"op": "crop", "width": 200, "height": 200, "x": 20, "y": 20},
                         {"op": "flip_h"}, {"op": "flip_v"}, {"op": "fps", "fps": 15}])
        self.assertEqual((out["width"], out["height"]), (200, 200))
        self.assertEqual(out["fps"], 15)

    def test_reverse(self):
        out = apply_ops(self.clip, self.out("rev.mp4"), [{"op": "reverse"}])
        self.assertAlmostEqual(out["duration"], 4, delta=0.3)
        self.assertTrue(out["has_audio"])
        self.assertTrue(os.path.getsize(self.out("rev.mp4")) > 1000)

    def test_invert(self):
        out = apply_ops(self.clip, self.out("inv.mp4"), [{"op": "invert"}])
        self.assertAlmostEqual(out["duration"], 4, delta=0.3)
        self.assertTrue(out["has_audio"])
        self.assertTrue(os.path.getsize(self.out("inv.mp4")) > 1000)

    def test_sepia(self):
        out = apply_ops(self.clip, self.out("sepia.mp4"), [{"op": "sepia", "intensity": 1}])
        self.assertAlmostEqual(out["duration"], 4, delta=0.3)
        self.assertTrue(out["has_audio"])
        self.assertTrue(os.path.getsize(self.out("sepia.mp4")) > 1000)

    def test_pad(self):
        out = apply_ops(self.clip, self.out("pad.mp4"), [{"op": "pad", "width": 400, "height": 300}])
        self.assertEqual((out["width"], out["height"]), (400, 300))
        self.assertAlmostEqual(out["duration"], 4, delta=0.3)
        self.assertTrue(os.path.getsize(self.out("pad.mp4")) > 1000)

    def test_noise(self):
        out = apply_ops(self.clip, self.out("noise.mp4"), [{"op": "noise", "strength": 30}])
        self.assertAlmostEqual(out["duration"], 4, delta=0.3)
        self.assertTrue(out["has_audio"])
        self.assertTrue(os.path.getsize(self.out("noise.mp4")) > 1000)

    def test_pixelate(self):
        out = apply_ops(self.clip, self.out("pix.mp4"), [{"op": "pixelate", "block": 16}])
        self.assertAlmostEqual(out["duration"], 4, delta=0.3)
        self.assertTrue(out["has_audio"])
        self.assertTrue(os.path.getsize(self.out("pix.mp4")) > 1000)

    def test_loop(self):
        out = apply_ops(self.clip, self.out("loop.mp4"), [{"op": "loop", "times": 2}])
        self.assertAlmostEqual(out["duration"], 8, delta=0.4)
        self.assertTrue(out["has_audio"])
        self.assertTrue(os.path.getsize(self.out("loop.mp4")) > 1000)

    def test_audio_ops(self):
        out = apply_ops(self.clip, self.out("a.mp4"),
                        [{"op": "volume", "factor": 0.5},
                         {"op": "fade_in", "duration": 0.5},
                         {"op": "fade_out", "duration": 0.5}])
        self.assertTrue(out["has_audio"])
        muted = apply_ops(self.clip, self.out("m.mp4"), [{"op": "mute"}])
        self.assertFalse(muted["has_audio"])

    def test_extract_audio(self):
        out = apply_ops(self.clip, self.out("a.mp3"), [{"op": "extract_audio", "format": "mp3"}])
        self.assertTrue(os.path.getsize(self.out("a.mp3")) > 1000)
        self.assertEqual(out["format"], "mp3")

    def test_thumbnail_and_text(self):
        out = apply_ops(self.clip, self.out("thumb.png"),
                        [{"op": "thumbnail", "time": 2, "width": 160}])
        self.assertTrue(os.path.getsize(self.out("thumb.png")) > 100)
        out2 = apply_ops(self.clip, self.out("txt.mp4"),
                         [{"op": "text", "text": "hola", "fontsize": 24}])
        self.assertTrue(os.path.getsize(self.out("txt.mp4")) > 1000)

    def test_gif_and_compress(self):
        out = apply_ops(self.clip, self.out("c.gif"),
                        [{"op": "gif", "start": 0, "duration": 1, "fps": 10, "width": 160}])
        self.assertTrue(os.path.getsize(self.out("c.gif")) > 1000)
        out2 = apply_ops(self.clip, self.out("comp.mp4"), [{"op": "compress", "crf": 28}])
        self.assertTrue(os.path.getsize(self.out("comp.mp4")) > 1000)

    def test_join(self):
        out = join_videos([self.clip, self.clip], self.out("joined.mp4"))
        self.assertAlmostEqual(out["duration"], 8, delta=0.5)

    def test_unknown_op_and_bad_param(self):
        with self.assertRaises(ValueError):
            apply_ops(self.clip, self.out("x.mp4"), [{"op": "nope"}])
        with self.assertRaises(ValueError):
            apply_ops(self.clip, self.out("x.mp4"), [{"op": "brightness", "value": 5}])
        with self.assertRaises(ValueError):
            apply_ops(self.clip, self.out("x.mp4"), [{"op": "trim", "start": 3, "end": 1}])

    def test_cli(self):
        res = subprocess.run([sys.executable, "-m", "vidforge.cli", "ops"],
                             capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."))
        # cli module path: run as installed script instead
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertGreaterEqual(len(json.loads(res.stdout)), 24)


if __name__ == "__main__":
    unittest.main()
