"""What ledger-truth does, in one run. Works without FinQA on disk.

python demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ledgertruth import corpus  # noqa: E402
from ledgertruth import program as P  # noqa: E402

print("FinQA's arithmetic language, executed")
for prog, gold in [
    ("subtract(5829, 5735)", 94.0),
    ("subtract(5829, 5735), divide(#0, 5735)", 0.01639),
    ("divide(9896, 23.6%)", 41932.2),
    ("greater(5829, 5735)", "yes"),
]:
    result = P.run(prog)
    print(
        f"  {prog:<38} -> {result.value:<12.6g} gold {gold!s:<9}"
        f"{'agrees' if P.matches_answer(result.value, gold) else 'DIFFERS'}"
    )
print(
    f"  {'table_average(revenue, none)':<38} -> "
    f"{P.run('table_average(revenue, none)', [['revenue', '$ 10', '$ 20']]).value:g}"
)

if all(corpus.available(s) for s in corpus.SPLITS):
    print("\nFinQA questions whose program needs a number found nowhere on the page")
    for split in corpus.SPLITS:
        qs = corpus.load(split)
        flagged = [q for q in qs if q.unsourceable]
        print(
            f"  {split:<6}{len(flagged):>5} of {len(qs):>5,}  {len(flagged) / len(qs):.1%}"
            f"   e.g. {flagged[0].id}  {flagged[0].program}"
        )
else:
    print(
        f"\nFinQA is not in {corpus.data_dir()}; run `python scripts/fetch_data.py` "
        "for the corpus numbers (scripts/measure.py prints every README table)."
    )
