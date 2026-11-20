"""Minimal MCP server over stdio. No dependencies, plain JSON-RPC.

Tools: edit_video, describe_video, list_operations, join_videos.
"""

import json
import sys

from . import __version__, apply_ops, describe, join_videos, list_ops

TOOLS = [
    {
        "name": "edit_video",
        "description": "Apply a list of video operations and save the result. Ops are the same ones list_operations returns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input video path"},
                "output": {"type": "string", "description": "Output video path"},
                "ops": {"type": "array", "items": {"type": "object"}, "description": "Ops to apply, e.g. [{\"op\": \"trim\", \"start\": 2, \"end\": 8}]"},
            },
            "required": ["input", "output", "ops"],
        },
    },
    {
        "name": "describe_video",
        "description": "Get duration, size, fps and codecs of a video.",
        "inputSchema": {
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Video path"}},
            "required": ["input"],
        },
    },
    {
        "name": "list_operations",
        "description": "List every operation with its parameters and valid ranges.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "join_videos",
        "description": "Join two or more videos into one, in order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inputs": {"type": "array", "items": {"type": "string"}, "description": "Input videos in order"},
                "output": {"type": "string", "description": "Output video path"},
            },
            "required": ["inputs", "output"],
        },
    },
]


def _text(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def _call(name, args):
    if name == "list_operations":
        return _text(list_ops())
    if name == "describe_video":
        return _text(describe(args["input"]))
    if name == "edit_video":
        return _text(apply_ops(args["input"], args["output"], args["ops"]))
    if name == "join_videos":
        return _text(join_videos(args["inputs"], args["output"]))
    raise ValueError(f"unknown tool '{name}'")


def run():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method", "")
        req_id = req.get("id")
        if method in ("notifications/initialized", "notifications/cancelled"):
            continue
        if method == "initialize":
            result = {
                "protocolVersion": req.get("params", {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vidforge", "version": __version__},
            }
            resp = {"result": result}
        elif method == "ping":
            resp = {"result": {}}
        elif method == "tools/list":
            resp = {"result": {"tools": TOOLS}}
        elif method == "tools/call":
            try:
                resp = {"result": _call(req["params"]["name"], req["params"].get("arguments", {}))}
            except Exception as e:
                resp = {"result": {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}], "isError": True}}
        else:
            resp = {"error": {"code": -32601, "message": f"method not found: {method}"}}
        if req_id is not None:
            print(json.dumps({"jsonrpc": "2.0", "id": req_id, **resp}), flush=True)
