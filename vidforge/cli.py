"""vidforge command line. Built for agents: JSON in, JSON out."""

import argparse
import json
import sys

from . import __version__, apply_ops, describe, join_videos, list_ops


def _fail(msg):
    print(json.dumps({"error": msg}), file=sys.stderr)
    raise SystemExit(1)


def _ok(payload):
    print(json.dumps(payload))


def cmd_edit(args):
    try:
        ops = json.loads(args.ops)
        result = apply_ops(args.input, args.output, ops)
    except (ValueError, RuntimeError, json.JSONDecodeError) as e:
        _fail(str(e))
    _ok(result)


def cmd_ops(args):
    _ok(list_ops())


def cmd_describe(args):
    try:
        result = describe(args.input)
    except ValueError as e:
        _fail(str(e))
    _ok(result)


def cmd_join(args):
    try:
        result = join_videos(args.inputs, args.output)
    except (ValueError, RuntimeError) as e:
        _fail(str(e))
    _ok(result)


def cmd_mcp(args):
    from .mcp_server import run

    run()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vidforge", description="Video editing for AI agents.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_edit = sub.add_parser("edit", help="Apply operations to a video and save the result.")
    p_edit.add_argument("-i", "--input", required=True, help="Input video path")
    p_edit.add_argument("-o", "--output", required=True, help="Output video path")
    p_edit.add_argument("--ops", required=True, help='JSON list of ops, e.g. \'[{"op": "trim", "start": 2, "end": 8}]\'')
    p_edit.set_defaults(func=cmd_edit)

    p_ops = sub.add_parser("ops", help="List every operation with its parameters.")
    p_ops.set_defaults(func=cmd_ops)

    p_desc = sub.add_parser("describe", help="Print video info as JSON.")
    p_desc.add_argument("-i", "--input", required=True, help="Input video path")
    p_desc.set_defaults(func=cmd_describe)

    p_join = sub.add_parser("join", help="Join two or more videos into one.")
    p_join.add_argument("-i", "--inputs", nargs="+", required=True, help="Input videos in order")
    p_join.add_argument("-o", "--output", required=True, help="Output video path")
    p_join.set_defaults(func=cmd_join)

    p_mcp = sub.add_parser("mcp", help="Start the MCP server on stdio.")
    p_mcp.set_defaults(func=cmd_mcp)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
