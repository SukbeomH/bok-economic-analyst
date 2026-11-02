"""Print local PDF text search results as JSON."""

import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys

from bok_documents import search_documents, search_result_payload


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    """Return 0 for search outcomes and 2 for JSON errors written to stderr."""
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Search PDF text without Azure or an index")
    search.add_argument("query")
    search.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    search.add_argument("--limit", type=int, default=5)
    try:
        args = parser.parse_args(argv)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = search_documents(args.query, args.data_dir, args.limit)
    except (ValueError, OSError) as error:
        print(json.dumps({"ok": False, "error": {"code": "invalid_input", "message": str(error)}},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(search_result_payload(result), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
