"""GravixLayer CLI entry point.

Usage:
    gravixlayer runtime create --template python-base-v1
    gravixlayer runtime list
    gravixlayer runtime run-cmd <runtime_id> "ls -la"
    gravixlayer runtime run-code <runtime_id> "print('hello')"
    gravixlayer template build my-env --from-image python:3.11-slim --pip-install numpy pandas
    gravixlayer template list
"""

import argparse
import sys

from .. import __version__
from .cmd_runtime import register_runtime_parser
from .cmd_template import register_template_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gravixlayer",
        description="GravixLayer CLI — manage cloud runtimes and templates",
    )
    parser.add_argument(
        "--version", "-V", action="version", version=f"gravixlayer {__version__}",
    )

    # Global connection flags (available to all subcommands)
    parser.add_argument("--api-key", dest="api_key", help="API key (or set GRAVIXLAYER_API_KEY)")
    parser.add_argument("--base-url", dest="base_url", help="API base URL (or set GRAVIXLAYER_BASE_URL)")
    parser.add_argument("--cloud", help="Default cloud provider (or set GRAVIXLAYER_CLOUD)")
    parser.add_argument("--region", help="Default region (or set GRAVIXLAYER_REGION)")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP request timeout in seconds (default: 60)")
    parser.add_argument("--json", action="store_true", default=False, help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command")
    register_runtime_parser(subparsers)
    register_template_parser(subparsers)

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if not hasattr(args, "func"):
        parser.parse_args([args.command, "--help"])
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
