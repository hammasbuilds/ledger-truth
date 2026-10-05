"""Command line: run a FinQA program, or list the questions that cannot be sourced.

python -m ledgertruth run "divide(9896, 23.6%)"
python -m ledgertruth unsourceable --split test --json
"""

from __future__ import annotations

import argparse
import json
import sys

from . import corpus
from . import program as P


def _run(args: argparse.Namespace) -> int:
    table = None
    if args.table:
        try:
            with open(args.table, encoding="utf-8") as handle:
                table = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read table {args.table}: {exc}", file=sys.stderr)
            return 2
        if not isinstance(table, list) or not all(isinstance(r, list) for r in table):
            print("error: --table must be a JSON list of rows (lists of strings)", file=sys.stderr)
            return 2
        table = [[str(c) for c in row] for row in table]
    result = P.run(args.program, table)
    if args.json:
        print(json.dumps({"program": args.program, "status": result.status, "value": result.value}))
    elif result.ran:
        print(f"{result.value:g}")
    else:
        print(f"not run: {result.status}", file=sys.stderr)
    return 0 if result.ran else 1


def _unsourceable(args: argparse.Namespace) -> int:
    try:
        questions = corpus.load(args.split)
    except corpus.CorpusMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rows = []
    for q in questions:
        missing = q.unsourceable if not args.filing_only else q.ungrounded
        if missing:
            rows.append({"id": q.id, "program": q.program, "missing": list(missing)})
    if args.json:
        json.dump(
            {"split": args.split, "questions": len(questions), "flagged": len(rows), "items": rows},
            sys.stdout,
            indent=1,
        )
        print()
    else:
        for row in rows:
            print(f"{row['id']}\t{row['program']}\tmissing {row['missing']}")
        print(
            f"{len(rows)} of {len(questions)} ({len(rows) / len(questions):.1%})", file=sys.stderr
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledgertruth", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="execute one FinQA program")
    run.add_argument("program")
    run.add_argument("--table", help="JSON file: list of rows, first cell is the label")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=_run)

    uns = sub.add_parser("unsourceable", help="questions whose program needs an absent number")
    uns.add_argument("--split", choices=corpus.SPLITS, default="train")
    uns.add_argument(
        "--filing-only",
        action="store_true",
        help="flag numbers absent from the filing even if the question has them",
    )
    uns.add_argument("--json", action="store_true")
    uns.set_defaults(func=_unsourceable)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
