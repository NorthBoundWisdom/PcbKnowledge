"""Explicit object-storage deployment commands."""

import argparse
import json
from collections.abc import Sequence

from pydantic import ValidationError

from pcbknowledge.platform.config import get_object_storage_settings
from pcbknowledge.platform.storage import ObjectStoreUnavailableError, initialize_object_storage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcbknowledge-storage")
    parser.add_subparsers(dest="command", required=True).add_parser(
        "init",
        help="idempotently create and probe the configured private object bucket",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one storage deployment command without printing endpoints or secrets."""

    arguments = _build_parser().parse_args(argv)
    if arguments.command != "init":
        raise AssertionError("argparse accepted an unknown storage command")
    try:
        created = initialize_object_storage(get_object_storage_settings())
    except ValidationError, ObjectStoreUnavailableError:
        print(json.dumps({"status": "failed"}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {"bucket": "created" if created else "present", "status": "ready"},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
