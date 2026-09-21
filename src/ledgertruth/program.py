"""FinQA's little arithmetic language, and an executor for it.

A FinQA answer is not a span. It is a program:

    subtract(5829, 5735)
    divide(subtract(5829, 5735), 5735)

Operands are literals lifted from the filing, or `#0`, `#1` … referring back to
earlier steps. Ten operators cover the whole training set: divide, subtract,
add, multiply, greater, exp, and four that fold a table row — table_sum,
table_average, table_max, table_min.

Executing the gold programs is the point. A benchmark that ships both a program
and the answer it is supposed to produce can be checked against itself, and a
question whose own gold program does not reach its own gold answer is not a
question anyone can be marked on.

The table operators need the filing's table, so they are only executed when one
is supplied; otherwise they report `TABLE_OP` rather than guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STEP = re.compile(r"([a-z_]+)\(([^()]*)\)")
REFERENCE = re.compile(r"^#(\d+)$")
# "$ 5,829.5", "( 1,234 )" for negatives, "12.3%".
NUMBER = re.compile(r"^\(?\s*[-+]?\$?\s*[\d,]+(?:\.\d+)?\s*%?\s*\)?$")

TABLE_OPS = frozenset({"table_sum", "table_average", "table_max", "table_min"})
BINARY_OPS = frozenset({"add", "subtract", "multiply", "divide", "greater", "exp"})

OK = "ok"
TABLE_OP = "table_op"
BAD_PROGRAM = "bad_program"
DIVIDE_BY_ZERO = "divide_by_zero"


@dataclass(frozen=True)
class Result:
    """What running a program produced, and why it did not if it did not."""

    status: str
    value: float | None = None

    @property
    def ran(self) -> bool:
        return self.status == OK


def as_number(raw: str) -> float | None:
    """Read a filing's way of writing a number.

    Two conventions change the value rather than the formatting, and both were
    wrong here first:

    * **Parentheses mean negative** in financial statements.
    * **A trailing `%` means divide by a hundred.** FinQA's programs mix the
      two freely — `divide(9896, 23.6%)` has a gold answer of 41932.2, which is
      9896/0.236. Reading `23.6%` as 23.6 gives 419.3 and looks like benchmark
      noise rather than a parser bug.
    """
    text = raw.strip()
    if not NUMBER.match(text):
        return None
    negative = text.startswith("(") and text.endswith(")")
    percent = "%" in text
    cleaned = text.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if percent:
        value /= 100
    return -value if negative else value


def steps(program: str) -> list[tuple[str, list[str]]]:
    """Split a program into (operator, operands), outermost last.

    FinQA writes them already flattened and comma-separated, so this is a scan
    rather than a parse.
    """
    out = []
    for operator, arguments in STEP.findall(program or ""):
        operands = [a.strip() for a in arguments.split(",") if a.strip()]
        out.append((operator, operands))
    return out


def run(program: str, table: list[list[str]] | None = None) -> Result:
    """Execute a gold program. Returns the value of its last step."""
    parsed = steps(program)
    if not parsed:
        return Result(BAD_PROGRAM)

    values: list[float] = []
    for operator, operands in parsed:
        if operator in TABLE_OPS:
            if table is None:
                return Result(TABLE_OP)
            folded = _fold(operator, operands, table)
            if folded is None:
                return Result(BAD_PROGRAM)
            values.append(folded)
            continue

        if operator not in BINARY_OPS or len(operands) != 2:
            return Result(BAD_PROGRAM)

        resolved = []
        for operand in operands:
            reference = REFERENCE.match(operand)
            if reference:
                index = int(reference.group(1))
                if index >= len(values):
                    return Result(BAD_PROGRAM)
                resolved.append(values[index])
                continue
            number = as_number(operand)
            if number is None:
                if operand == "const_100":
                    resolved.append(100.0)
                    continue
                if operand.startswith("const_"):
                    constant = as_number(operand.removeprefix("const_").replace("m1", "-1"))
                    if constant is None:
                        return Result(BAD_PROGRAM)
                    resolved.append(constant)
                    continue
                return Result(BAD_PROGRAM)
            resolved.append(number)

        left, right = resolved
        if operator == "add":
            values.append(left + right)
        elif operator == "subtract":
            values.append(left - right)
        elif operator == "multiply":
            values.append(left * right)
        elif operator == "divide":
            if right == 0:
                return Result(DIVIDE_BY_ZERO)
            values.append(left / right)
        elif operator == "greater":
            values.append(1.0 if left > right else 0.0)
        elif operator == "exp":
            values.append(left**right)

    return Result(OK, values[-1])


def _fold(operator: str, operands: list[str], table: list[list[str]]) -> float | None:
    """Apply a table_* operator to the row whose label matches the operand."""
    if not operands:
        return None
    wanted = operands[0].strip().lower()
    for row in table:
        if row and row[0].strip().lower() == wanted:
            numbers = [n for n in (as_number(cell) for cell in row[1:]) if n is not None]
            if not numbers:
                return None
            if operator == "table_sum":
                return sum(numbers)
            if operator == "table_average":
                return sum(numbers) / len(numbers)
            if operator == "table_max":
                return max(numbers)
            if operator == "table_min":
                return min(numbers)
    return None


def agrees(got: float, expected: float, tolerance: float = 0.01) -> bool:
    """Whether two answers are the same number.

    Relative rather than absolute, because FinQA answers range from ratios like
    0.0163 to figures in the billions, and rounds its own gold answers to a
    couple of significant figures.
    """
    if expected == 0:
        return abs(got) < tolerance
    return abs(got - expected) / abs(expected) < tolerance


def matches_answer(value: float, gold) -> bool:
    """Compare a computed value against FinQA's gold answer field.

    `greater(...)` programs have a gold answer of the string "yes" or "no",
    not 1 or 0, so a numeric-only comparison marks every comparison question
    wrong — 124 of them in train, which reads as a 2% benchmark defect and is
    nothing of the kind.
    """
    if isinstance(gold, str):
        text = gold.strip().lower()
        if text in ("yes", "no"):
            return (value == 1.0) == (text == "yes")
        number = as_number(text)
        return number is not None and agrees(value, number)
    if isinstance(gold, (int, float)):
        return agrees(value, float(gold))
    return False
