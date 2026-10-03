"""The executor, on cases small enough to check by hand.

Two of these encode conventions that are not documented anywhere in FinQA and
that cost 5.2 percentage points of apparent benchmark quality when missed.
"""

from __future__ import annotations

import pytest

from ledgertruth import program as P


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1234", 1234.0),
        ("1,234", 1234.0),
        ("$ 5829", 5829.0),
        ("$ 2309.9", 2309.9),
        ("( 6.1 )", -6.1),
        ("-2.5", -2.5),
    ],
)
def test_reads_a_filings_number(raw, expected):
    assert P.as_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw,expected", [("23.6%", 0.236), ("14.6%", 0.146), ("2%", 0.02)])
def test_percent_scales_by_a_hundred(raw, expected):
    """divide(9896, 23.6%) has a gold answer of 41932, which is 9896/0.236.

    Reading 23.6% as 23.6 gives 419 and looks like a broken benchmark.
    """
    assert P.as_number(raw) == pytest.approx(expected)


def test_parentheses_mean_negative_not_grouping():
    assert P.as_number("( 1,222 )") == -1222.0


def test_words_are_not_numbers():
    assert P.as_number("fourth quarter") is None
    assert P.as_number("") is None


def test_single_step():
    assert P.run("subtract(5829, 5735)").value == pytest.approx(94.0)


def test_step_references():
    result = P.run("subtract(5829, 5735), divide(#0, 5735)")
    assert result.ran
    assert result.value == pytest.approx(94 / 5735)


def test_constants():
    assert P.run("divide(3.1, const_1000)").value == pytest.approx(0.0031)
    assert P.run("multiply(2, const_100)").value == pytest.approx(200.0)


def test_divide_by_zero_is_reported_not_raised():
    assert P.run("divide(1, 0)").status == P.DIVIDE_BY_ZERO


def test_unparseable_program_is_reported():
    assert P.run("").status == P.BAD_PROGRAM
    assert P.run("frobnicate(1, 2)").status == P.BAD_PROGRAM


def test_forward_reference_is_rejected():
    """#1 before step 1 exists must not silently read the wrong value."""
    assert P.run("add(#1, 2)").status == P.BAD_PROGRAM


def test_greater_answers_yes_and_no():
    """FinQA's gold answer for a comparison is a word, not a number.

    Comparing numerically marks all 124 comparison questions in train wrong,
    which reads as a 2% benchmark defect and is nothing of the kind.
    """
    result = P.run("greater(189.57, 137.82)")
    assert result.ran
    assert P.matches_answer(result.value, "yes")
    assert not P.matches_answer(result.value, "no")
    assert P.matches_answer(P.run("greater(1, 2)").value, "no")


def test_table_ops_need_a_table():
    assert P.run("table_average(fourth quarter, none)").status == P.TABLE_OP


def test_table_average_folds_the_named_row():
    table = [["", "high", "low"], ["fourth quarter", "57.92", "45.68"]]
    assert P.run("table_average(fourth quarter, none)", table).value == pytest.approx(51.8)


def test_table_min_max_sum():
    table = [["revenue", "10", "30", "20"]]
    assert P.run("table_min(revenue, none)", table).value == 10
    assert P.run("table_max(revenue, none)", table).value == 30
    assert P.run("table_sum(revenue, none)", table).value == 60


def test_agrees_is_relative():
    """Gold answers are rounded, sometimes to one significant figure."""
    assert P.agrees(94.0001, 94.0)
    assert not P.agrees(94.0, 90.0)
    assert P.agrees(0.0, 0.0)


def test_nested_calls_are_rejected_not_half_run():
    """FinQA writes programs flat; a nested call used to return the inner step."""
    assert P.run("divide(subtract(5829, 5735), 5735)").status == P.BAD_PROGRAM
    assert P.run("subtract(5829, 5735) junk").status == P.BAD_PROGRAM
    assert P.agrees(P.run("subtract(5829, 5735), divide(#0, 5735)").value, 0.016390)
