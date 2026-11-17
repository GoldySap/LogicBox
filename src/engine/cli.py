import argparse
import json

from engine import Node, TerminalGraphicsDriver
from engine.render.pipeline import UniversalRenderPipeline


def main() -> int:
    parser = argparse.ArgumentParser(prog="logicbox", description="Universal Engine utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a serialized node tree")
    inspect_parser.add_argument("file")

    smoke_parser = subparsers.add_parser("smoke", help="Run a terminal rendering smoke test")
    smoke_parser.add_argument("--width", type=int, default=40)
    smoke_parser.add_argument("--height", type=int, default=10)

    args = parser.parse_args()
    if args.command == "inspect":
        root = Node.load_json(args.file)
        print(json.dumps(root.to_dict(), indent=2))
        return 0

    root = Node("root")
    pipeline = UniversalRenderPipeline(TerminalGraphicsDriver(args.width, args.height))
    pipeline.render_scene(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
