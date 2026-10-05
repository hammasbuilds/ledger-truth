# ledger-truth

> **7.6% of FinQA questions require a number that appears nowhere in the filing they were written against — nor in the question.** A system that only uses figures it can point to cannot answer them.

**Status:** complete as a measurement. No model is involved: FinQA ships both a program and
the answer that program should produce, so the benchmark can be checked by running it.

## The corpus

[FinQA](https://github.com/czyssrs/FinQA) — 8,281 questions written by finance
professionals over S&P 500 earnings filings. Each carries the page's table, the surrounding
prose, and a gold program in a small arithmetic language:

```
subtract(5829, 5735)
subtract(5829, 5735), divide(#0, 5735)
```

Steps are flat; `#0` refers to the first step's result.

| Split | Questions | 1-step | 2-step | 3+ | Answer already in filing |
|---|---:|---:|---:|---:|---:|
| train | 6,251 | 59.5% | 32.2% | 8.3% | **2.9%** |
| dev | 883 | 59.2% | 32.5% | 8.3% | 3.3% |
| test | 1,147 | 57.0% | 35.7% | 7.3% | 3.3% |

Unlike most extractive benchmarks, the answer is almost never sitting in the document. This
is arithmetic, and a retrieval baseline has nowhere to hide — which is why the corpus is
worth checking properly rather than leaderboarding.

```
python -m venv .venv && .venv/Scripts/activate    # source .venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
python demo.py                 # the executor on worked examples; works without the data
python scripts/fetch_data.py   # 103 MB from the authors' repo, not in git
python scripts/measure.py      # every table below
python -m pytest               # 50 tests
```

FinQA goes to `data/` by default. Set `LEDGERTRUTH_DATA=/some/dir` to keep it elsewhere;
`fetch_data.py`, `measure.py`, the library and the tests all read it. The fetch writes to
`<split>.json.part` and resumes an interrupted download on the next run.

Without the data, `pytest` runs 31 tests and skips the 19 that read FinQA, each with a
reason pointing at `fetch_data.py`.

## Command line

```
ledgertruth run "subtract(5829, 5735), divide(#0, 5735)"        # 0.0163906
ledgertruth run "table_average(revenue, none)" --table t.json  # t.json: [["revenue","$ 10","$ 20"]]
ledgertruth unsourceable --split test                          # id, program, missing literal(s)
ledgertruth unsourceable --split test --json                   # same, as JSON
```

`unsourceable` lists the questions behind the 7.6% figure below; `--filing-only` also keeps
those whose missing number is stated in the question (the 8.0% column). `python -m ledgertruth`
works the same. Exit status is 1 for a program that does not run, 2 for missing data or a bad
`--table` file.

From Python, `Question.unsourceable` and `Question.ungrounded` give the same two sets.

## Does the benchmark's own arithmetic work

| Split | Reproduces gold answer | Mismatch | Unparsed |
|---|---:|---:|---:|
| train | **99.2%** | 0.2% | 0.6% |
| dev | 98.0% | 0.6% | 1.5% |
| test | **99.2%** | 0.2% | 0.6% |

It does. Getting there needed two conventions that FinQA does not document:

- **A trailing `%` scales by 1/100.** `divide(9896, 23.6%)` has a gold answer of 41932,
  which is 9896/0.236. Reading `23.6%` as 23.6 gives 419.
- **`greater(...)` answers `"yes"`/`"no"`, not 1/0.**

Miss both and the train mismatch rate reads **5.4%** instead of 0.2% (dev 4.5%, test 4.7%;
`measure.py` prints this ablation) — which looks exactly like a
defective benchmark, and is not one. Both are pinned by tests.

## Numbers that come from nowhere

| Split | Questions | Literal absent from the filing | …and from the question too |
|---|---:|---:|---:|
| train | 6,251 | 8.0% | **7.6%** |
| dev | 883 | 6.5% | 6.0% |
| test | 1,147 | 7.9% | **7.7%** |

The gold program states a number that occurs nowhere on the page it was written against,
and nowhere in the question either.

```
AAL/2018/page_13.pdf-2     divide(9896, 23.6%)         23.6% is not on the page
MAS/2017/page_37.pdf-1     subtract(14.6%, 13.0%)      neither margin is on the page
FBHS/2017/page_46.pdf-2    divide(6.1, -2.5)           -2.5 is not on the page
AMT/2005/page_84.pdf-4     divide(646560, const_1000)  646560 is not on the page
```

FinQA gives one page of a report. The annotator knew these figures from the rest of the
filing, or computed them and wrote the result down as a literal. Either way the question is
not answerable from what the model is shown.

**This is the number that matters for anything financial.** A system that refuses to use a
figure it cannot source will get all of these wrong. A system that scores well on them is
producing numbers it cannot source — which is the failure mode that actually costs money,
and the one an aggregate accuracy hides completely.

## A smaller problem: row labels are not unique

`table_average(fourth quarter)` on a table listing two years has two answers. The gold
answer silently means the second.

| | |
|---|---:|
| `table_*` operations across all splits | 281 |
| naming a row label that occurs twice | **3** (1.1%) |
| …where the duplicate rows hold different values | **2** (0.7%) |

In the third case (PNC) the two rows are identical. In the two that differ, the gold answer
uses the second row and the executor takes the first, so both count as mismatches above. Rare. Worth knowing the program language permits it at all.

## Layout

```
scripts/fetch_data.py            FinQA from raw.githubusercontent, byte-ranged
src/ledgertruth/program.py       the arithmetic language and an executor for it
src/ledgertruth/corpus.py        questions, filings, and what numbers are in them
src/ledgertruth/__main__.py      the `ledgertruth` command
scripts/measure.py               every table above
demo.py                          worked examples, no data needed
tests/                           50 tests, incl. the executor on hand-checked cases
```

## Licence

Code: MIT, see [LICENSE](LICENSE). No dataset is committed; the fetch script downloads
each source under its own terms.
