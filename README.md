# vidforge

Cut, resize and filter video with ffmpeg, without writing ffmpeg flags by hand. You describe the edit as a list of ops; vidforge turns it into a single ffmpeg call and prints JSON back.

It shells out to ffmpeg, so install that first (`apt install ffmpeg` / `brew install ffmpeg`).

## Install

```sh
pip install vidforge
```

## Use it from the terminal

```sh
# what can it do?
vidforge ops

# describe a file
vidforge describe clip.mp4

# edit it: keep seconds 2-8, half speed, 720p, a bit warmer
vidforge edit -i clip.mp4 -o clip-edit.mp4 --ops '[
  {"op": "trim", "start": 2, "end": 8},
  {"op": "scale", "width": 1280, "height": -1},
  {"op": "saturation", "factor": 1.2}
]'
```

Output is JSON, so it is easy to parse:

```json
{"output": "clip-edit.mp4", "duration": 6.0, "width": 1280, "height": 720, "fps": 30.0, "has_audio": true, "ops_applied": ["trim", "scale", "saturation"]}
```

More one-liners:

```sh
# just the audio
vidforge edit -i clip.mp4 -o audio.mp3 --ops '[{"op": "extract_audio", "format": "mp3"}]'

# one frame as a thumbnail
vidforge edit -i clip.mp4 -o thumb.png --ops '[{"op": "thumbnail", "time": 3, "width": 640}]'

# a small gif
vidforge edit -i clip.mp4 -o clip.gif --ops '[{"op": "gif", "start": 1, "duration": 2, "fps": 10, "width": 320}]'

# stick clips together
vidforge join -i a.mp4 b.mp4 -o full.mp4
```

## How an agent uses it

You turn the user's words into ops. `vidforge ops` lists every operation with its parameters and valid ranges, so there is nothing to guess. The usual requests:

- "cut the first 5 seconds and make it vertical" -> trim, crop
- "make a gif of the best 2 seconds" -> gif
- "quieter, and fade out at the end" -> volume, fade_out

If the edit you need is not an op yet, CONTRIBUTING.md explains how to add it.

## Use it from Python

```python
from vidforge import apply_ops

out = apply_ops("clip.mp4", "clip-edit.mp4", [
    {"op": "trim", "start": 2, "end": 8},
    {"op": "grayscale"},
])
```

## MCP server

Any MCP client can use vidforge as tools, including join_videos:

```sh
vidforge mcp
```

It speaks MCP over stdio and exposes `edit_video`, `describe_video`, `list_operations` and `join_videos`. Example client config:

```json
{
  "mcpServers": {
    "vidforge": {"command": "vidforge", "args": ["mcp"]}
  }
}
```

## License

MIT
