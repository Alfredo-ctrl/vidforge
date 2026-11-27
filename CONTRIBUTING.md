# Contributing

vidforge grows by adding operations. An operation is one function in `vidforge/ops.py` plus one entry in the `OPS` dict: name, a one-line description, and a params schema (type, default, min/max or enum).

Rules:

- One op does one thing. Keep it under 15 lines if you can.
- Never break the JSON contract: `vidforge ops` must keep working, and every op must run on videos with and without audio.
- Add a test in `tests/test_ops.py` that runs the op on the fixture video.
- Run `pytest` before opening a PR.

That's it.
