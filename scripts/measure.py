"""Every number in the README.

    python scripts/measure.py

No model. FinQA ships both a program and the answer that program is supposed to
produce, so the benchmark can be checked against itself by running it.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ledgertruth import corpus  # noqa: E402
from ledgertruth import program as P  # noqa: E402


def rule(title: str) -> None:
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)


def the_corpus() -> None:
    rule("the corpus")
    print(f"{'split':<8}{'questions':>11}{'1-step':>9}{'2-step':>9}{'3+':>7}"
          f"{'answer already in filing':>26}")
    for split in corpus.SPLITS:
        qs = corpus.load(split)
        lengths = collections.Counter(min(q.steps_count, 3) for q in qs)
        read_off = sum(1 for q in qs if q.answer_is_in_the_table)
        print(f"{split:<8}{len(qs):>11,}{lengths[1] / len(qs):>9.1%}"
              f"{lengths[2] / len(qs):>9.1%}{lengths[3] / len(qs):>7.1%}"
              f"{read_off / len(qs):>26.1%}")
    print("\n  ^ unlike most extractive benchmarks, the answer is almost never")
    print("    sitting in the document: 3% of the time. This is arithmetic, and")
    print("    a retrieval baseline has nowhere to hide.")


def the_self_check() -> None:
    rule("does the benchmark's own arithmetic work")
    print(f"{'split':<8}{'reproduces':>12}{'mismatch':>11}{'unparsed':>11}")
    for split in corpus.SPLITS:
        qs = corpus.load(split)
        st = collections.Counter()
        for q in qs:
            result = P.run(q.program, [list(r) for r in q.table])
            if not result.ran:
                st[result.status] += 1
            elif P.matches_answer(result.value, q.answer):
                st["ok"] += 1
            else:
                st["bad"] += 1
        print(f"{split:<8}{st['ok'] / len(qs):>12.1%}{st['bad'] / len(qs):>11.1%}"
              f"{st['bad_program'] / len(qs):>11.1%}")

    print("\nwithout the two conventions (% read as-is, gold compared as numbers only)")
    print(f"{'split':<8}{'mismatch':>11}")
    for split in corpus.SPLITS:
        qs = corpus.load(split)
        bad = 0
        for q in qs:
            result = P.run(q.program.replace("%", ""), [list(r) for r in q.table])
            if result.ran and not (
                isinstance(q.answer, (int, float))
                and not isinstance(q.answer, bool)
                and P.agrees(result.value, float(q.answer))
            ):
                bad += 1
        print(f"{split:<8}{bad / len(qs):>11.1%}")
    print("\n  ^ 99% of gold programs reach their own gold answer. Getting there")
    print("    needed two conventions that are not written down anywhere:")
    print("      * a trailing % scales by 1/100 — divide(9896, 23.6%) is 41932,")
    print("        so 23.6% means 0.236 and reading it as 23.6 gives 419")
    print("      * greater(...) has a gold answer of 'yes'/'no', not 1/0")
    print("    Without them the mismatch rate reads 5.4% instead of 0.2%, which")
    print("    looks exactly like a defective benchmark.")


def the_ungrounded() -> None:
    rule("numbers that come from nowhere")
    print(f"{'split':<8}{'questions':>11}{'absent from filing':>21}"
          f"{'...and from the question':>26}")
    for split in corpus.SPLITS:
        qs = corpus.load(split)
        bad = [q for q in qs if q.ungrounded]
        unsourceable = sum(1 for q in bad if q.unsourceable)
        print(f"{split:<8}{len(qs):>11,}{len(bad) / len(qs):>21.1%}"
              f"{unsourceable / len(qs):>26.1%}")

    print("\n  ^ the gold program states a number that occurs nowhere in the page")
    print("    it was written against, nor in the question. The annotator knew it")
    print("    from the rest of the report, or worked it out and wrote the result")
    print("    down as a literal.")
    print("\n    A system that only uses numbers it can point to cannot answer")
    print("    these. A system that scores well on them is producing figures it")
    print("    cannot source — which, in a financial setting, is the failure that")
    print("    matters most.")

    qs = corpus.load("train")
    examples = [q for q in qs if q.ungrounded][:4]
    print()
    for q in examples:
        print(f"    {q.id[:30]:<32}{q.program[:40]:<42}missing {q.ungrounded[:2]}")


def the_table_ops() -> None:
    rule("a smaller problem: row labels are not unique")
    total = ambiguous = differing = 0
    for split in corpus.SPLITS:
        for q in corpus.load(split):
            for operator, operands in P.steps(q.program):
                if operator in P.TABLE_OPS and operands:
                    total += 1
                    wanted = operands[0].strip().lower()
                    hits = [
                        tuple(row) for row in q.table
                        if row and row[0].strip().lower() == wanted
                    ]
                    ambiguous += len(hits) > 1
                    differing += len(set(hits)) > 1
    print(f"table_* operations across all splits       {total:>6}")
    print(f"  naming a row label that occurs twice     {ambiguous:>6}   "
          f"{ambiguous / total:.1%}")
    print(f"  ...where the duplicate rows hold different values {differing:>2}   "
          f"{differing / total:.1%}")
    print("\n  ^ table_average('fourth quarter') on a table listing two years has")
    print("    two answers, and the gold answer silently means the second. Rare,")
    print("    and worth knowing the program language allows it at all. The executor")
    print("    takes the first matching row, so those questions count as mismatches.")


def main() -> None:
    missing = [s for s in corpus.SPLITS if not corpus.available(s)]
    if missing:
        print(f"FinQA split(s) {', '.join(missing)} not found in {corpus.data_dir()}.\n"
              f"Run `python scripts/fetch_data.py` first (or set {corpus.DATA_ENV}).",
              file=sys.stderr)
        raise SystemExit(2)
    the_corpus()
    the_self_check()
    the_ungrounded()
    the_table_ops()
    print()


if __name__ == "__main__":
    main()
