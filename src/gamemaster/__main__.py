from __future__ import annotations

import argparse
from pathlib import Path

from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GameMaster channel gateway agent.")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the HTTP channel gateway server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.add_argument("--data", type=Path, default=None)

    args = parser.parse_args()
    if args.command in (None, "serve"):
        serve(host=args.host, port=args.port, data_path=args.data)


if __name__ == "__main__":
    main()
