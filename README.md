# ledger-truth

A check of the FinQA benchmark against itself. We built it for anyone who trains or scores financial
question-answering systems on FinQA: it runs every gold program in FinQA's arithmetic language, confirms the
benchmark reproduces its own answers, and finds the questions whose program needs a number that appears nowhere in
the filing page or the question. **7.6% of FinQA's training questions are like that**, so a system that only uses
figures it can point to cannot answer them. No model is involved.

## What it does

- **Executes FinQA programs** such as `subtract(5829, 5735), divide(#0, 5735)`, including `table_*` operations
  over the page's table, with the two conventions FinQA does not document: a trailing `%` scales by 1/100
  (`divide(9896, 23.6%)` is 41932, not 419) and `greater(...)` answers `yes`/`no`.
- **Checks that each gold program reaches its gold answer**, per split.
- **Lists the unsourceable questions**: those whose program states a literal found nowhere on the page it was
  written against (`--filing-only` also keeps those where the number is in the question).
- **Finds ambiguous table references**: row labels that occur twice in one table.
- Downloads FinQA (103 MB) from the authors' repository by byte range, resuming an interrupted download.

## Sample input / output

`python demo.py` (works without the data; the second half reads FinQA once it is fetched):

```
FinQA's arithmetic language, executed
  subtract(5829, 5735)                   -> 94           gold 94.0     agrees
  subtract(5829, 5735), divide(#0, 5735) -> 0.0163906    gold 0.01639  agrees
  divide(9896, 23.6%)                    -> 41932.2      gold 41932.2  agrees
  greater(5829, 5735)                    -> 1            gold yes      agrees
  table_average(revenue, none)           -> 15

FinQA questions whose program needs a number found nowhere on the page
  train   474 of 6,251  7.6%   e.g. AAL/2018/page_13.pdf-2  divide(9896, 23.6%)
  dev      53 of   883  6.0%   e.g. ETR/2011/page_341.pdf-3  add(18.9, 0.3)
  test     88 of 1,147  7.7%   e.g. GPN/2010/page_87.pdf-3  divide(6.3, 18.1)
```

`ledgertruth unsourceable --split test` (first rows of 88):

```
88 of 1147 (7.7%)
GPN/2010/page_87.pdf-3	divide(6.3, 18.1)	missing [6.3]
ABMD/2008/page_86.pdf-1	subtract(168, 56)	missing [56.0]
AON/2007/page_175.pdf-2	add(155, -141), add(#0, 4)	missing [-141.0]
ETR/2013/page_21.pdf-2	subtract(2045, 1854), divide(194, #0)	missing [194.0]
```

## Results

From `python scripts/measure.py` over the full FinQA corpus (8,281 questions over S&P 500 earnings filings).

**The benchmark's own arithmetic works:**

| Split | Questions | Reproduces gold answer | Mismatch | Unparsed | Mismatch without the two conventions |
|---|---:|---:|---:|---:|---:|
| train | 6,251 | **99.2%** | 0.2% | 0.6% | 5.4% |
| dev | 883 | 98.0% | 0.6% | 1.5% | 4.5% |
| test | 1,147 | **99.2%** | 0.2% | 0.6% | 4.7% |

**Numbers that come from nowhere:**

| Split | Literal absent from the filing page | ...and from the question too |
|---|---:|---:|
| train | 8.0% | **7.6%** |
| dev | 6.5% | 6.0% |
| test | 7.9% | **7.7%** |

Examples: `AAL/2018/page_13.pdf-2 divide(9896, 23.6%)` (23.6% is not on the page), `MAS/2017/page_37.pdf-1
subtract(14.6%, 13.0%)` (neither margin is on the page). FinQA gives one page of a report; the annotator knew
these figures from the rest of the filing.

**Ambiguous row labels:** of 281 `table_*` operations across all splits, 3 (1.1%) name a row label that occurs
twice, and in 2 (0.7%) the duplicate rows hold different values.

The answer is already sitting in the filing for only 2.9-3.3% of questions, so FinQA is an arithmetic benchmark,
not an extractive one.

## Tech stack

- Python 3.11+, standard library only (`json`, `re`, `urllib` for the byte-ranged download, `argparse`)
- A small parser and executor for FinQA's program language (`src/ledgertruth/program.py`)
- pytest and ruff for development; CI on Ubuntu and Windows

## Run it

```bash
python -m venv .venv && .venv/Scripts/activate    # source .venv/bin/activate on Linux/macOS
pip install -e ".[dev]"
python demo.py                 # the executor on worked examples; works without the data
python scripts/fetch_data.py   # 103 MB of FinQA from the authors' repo, not in git
python scripts/measure.py      # every table above
python -m pytest               # 50 tests
```

FinQA goes to `data/` by default; set `LEDGERTRUTH_DATA=/some/dir` to keep it elsewhere. Without the data, `pytest`
runs 31 tests and skips the 19 that read FinQA.

```bash
ledgertruth run "subtract(5829, 5735), divide(#0, 5735)"        # 0.0163906
ledgertruth run "table_average(revenue, none)" --table t.json  # t.json: [["revenue","$ 10","$ 20"]]
ledgertruth unsourceable --split test                          # id, program, missing literal(s)
ledgertruth unsourceable --split test --json                   # same, as JSON
```

Exit status is 1 for a program that does not run, 2 for missing data or a bad `--table` file. From Python,
`Question.unsourceable` and `Question.ungrounded` give the same two sets.

## Licence

Code: MIT, see [LICENSE](LICENSE). No dataset is committed; `fetch_data.py` downloads
[FinQA](https://github.com/czyssrs/FinQA) (Chen et al., 2021) under its own terms.
