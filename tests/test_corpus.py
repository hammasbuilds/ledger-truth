"""Against the real FinQA files.

The headline test is `test_the_benchmark_reproduces_its_own_answers`: a
benchmark that ships programs and answers should agree with itself, and if it
stops doing so every number in the README is about something else.
"""

from __future__ import annotations

import pytest

from ledgertruth import corpus
from ledgertruth import program as P

# Everything here reads FinQA. A fresh clone does not have it, so the module
# skips (not fails) until scripts/fetch_data.py has run. Point LEDGERTRUTH_DATA
# at an empty directory to check the suite is hermetic.
pytestmark = pytest.mark.skipif(
    not all(corpus.available(s) for s in corpus.SPLITS),
    reason=f"FinQA not in {corpus.data_dir()}; run `python scripts/fetch_data.py` "
    f"(or set {corpus.DATA_ENV})",
)

SIZES = {"train": 6_251, "dev": 883, "test": 1_147}


@pytest.mark.parametrize("split,expected", SIZES.items())
def test_split_sizes(split, expected):
    assert len(corpus.load(split)) == expected


def test_unknown_split_is_rejected():
    with pytest.raises(ValueError):
        corpus.load("validation")


@pytest.mark.parametrize("split", SIZES)
def test_every_question_has_a_question_and_a_program(split):
    qs = corpus.load(split)
    assert all(q.question.strip() for q in qs)
    assert sum(1 for q in qs if not q.program.strip()) / len(qs) < 0.02


@pytest.mark.parametrize("split", SIZES)
def test_the_benchmark_reproduces_its_own_answers(split):
    """At least 97% of gold programs reach their own gold answer."""
    qs = corpus.load(split)
    ok = 0
    for q in qs:
        result = P.run(q.program, [list(r) for r in q.table])
        if result.ran and P.matches_answer(result.value, q.answer):
            ok += 1
    assert ok / len(qs) > 0.97, f"{split}: only {ok / len(qs):.1%}"


@pytest.mark.parametrize("split", SIZES)
def test_the_answer_is_almost_never_just_sitting_there(split):
    """Unlike an extractive benchmark, retrieval has nowhere to hide here."""
    qs = corpus.load(split)
    read_off = sum(1 for q in qs if q.answer_is_in_the_table) / len(qs)
    assert read_off < 0.10


@pytest.mark.parametrize("split", SIZES)
def test_some_programs_use_numbers_that_are_not_in_the_filing(split):
    """The finding. Between 6% and 9% depending on the split."""
    qs = corpus.load(split)
    share = sum(1 for q in qs if q.ungrounded) / len(qs)
    assert 0.03 < share < 0.15, share


def test_numbers_are_found_in_both_the_table_and_the_text():
    """Regression for a bug that lived in a shell command, not in the code.

    Passing the number regex through a double-quoted shell string mangled its
    backslashes, so no number in the prose was ever matched and the ungrounded
    rate read 38.8% instead of 8.0%. The pattern now lives in a module
    constant, and this checks it reaches the text.
    """
    q = next(x for x in corpus.load("train") if x.id == "GIS/2008/page_83.pdf-1")
    numbers = q.numbers
    # Both operands of subtract(2309.9, 2303.0) are in the prose, not the table.
    assert 2309.9 in numbers
    assert 2303.0 in numbers
    assert q.ungrounded == ()


def test_literals_exclude_references_and_constants():
    q = next(x for x in corpus.load("train") if "const_" in x.program and "#0" in x.program)
    assert all(isinstance(v, float) for v in q.literals)


def test_unsourceable_is_the_headline_definition():
    """`unsourceable` drops questions that state the missing number themselves."""
    qs = corpus.load("train")
    share = sum(1 for q in qs if q.unsourceable) / len(qs)
    assert 0.070 < share < 0.080, share
    assert all(q.ungrounded for q in qs if q.unsourceable)
