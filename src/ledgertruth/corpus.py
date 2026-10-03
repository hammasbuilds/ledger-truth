"""FinQA: questions over earnings filings, with executable gold programs.

8,281 questions written by finance professionals over S&P 500 earnings
reports. Each carries the filing's table, the surrounding text, and a program
in FinQA's little arithmetic language that is supposed to produce the answer.

What makes it the right corpus here is that it can be checked against itself.
The program and the answer are both given, so the benchmark's own arithmetic is
verifiable without a model, and every literal in a program either occurs in the
filing or does not.

    from ledgertruth import corpus

    train = corpus.load("train")
    train[0].program        # 'subtract(5829, 5735)'
    train[0].numbers        # every number in the table and the text
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .program import TABLE_OPS, as_number, steps

DATA = Path(__file__).resolve().parents[2] / "data"
DATA_ENV = "LEDGERTRUTH_DATA"
SPLITS = ("train", "dev", "test")

# A number as a filing writes one: "$ 2309.9", "( 6.1 )", "23.6%", "1,234".
# Kept in a module constant rather than inline because passing this through a
# shell once mangled the backslashes and turned a 0% result into 38.8%.
NUMBER_IN_TEXT = re.compile(r"\(?\$?\s?[-+]?[\d,]+(?:\.\d+)?%?\)?")


class CorpusMissingError(FileNotFoundError):
    """FinQA is not on disk."""


@dataclass(frozen=True)
class Question:
    """One question, its filing, and its gold program."""

    id: str
    question: str
    program: str
    answer: object
    table: tuple[tuple[str, ...], ...]
    pre_text: tuple[str, ...]
    post_text: tuple[str, ...]

    @property
    def text(self) -> str:
        return " ".join(self.pre_text + self.post_text)

    @property
    def numbers(self) -> frozenset[float]:
        """Every number that occurs anywhere in the filing, rounded.

        Rounding to six places so that a literal written one way in a program
        and another in a cell still matches; nothing in FinQA turns on the
        seventh decimal.
        """
        found = set()
        for row in self.table:
            for cell in row:
                value = as_number(cell)
                if value is not None:
                    found.add(round(value, 6))
        for line in self.pre_text + self.post_text:
            for token in NUMBER_IN_TEXT.findall(line):
                value = as_number(token)
                if value is not None:
                    found.add(round(value, 6))
        return frozenset(found)

    @property
    def literals(self) -> tuple[float, ...]:
        """The numbers a program states outright, excluding refs and constants."""
        out = []
        for operator, operands in steps(self.program):
            if operator in TABLE_OPS:
                continue
            for operand in operands:
                if operand.startswith("#") or operand.startswith("const_"):
                    continue
                value = as_number(operand)
                if value is not None:
                    out.append(round(value, 6))
        return tuple(out)

    @property
    def ungrounded(self) -> tuple[float, ...]:
        """Literals the program uses that occur nowhere in the filing."""
        present = self.numbers
        return tuple(v for v in self.literals if v not in present)

    @property
    def question_numbers(self) -> frozenset[float]:
        """Every number written in the question itself, rounded like `numbers`."""
        found = set()
        for token in NUMBER_IN_TEXT.findall(self.question):
            value = as_number(token)
            if value is not None:
                found.add(round(value, 6))
        return frozenset(found)

    @property
    def unsourceable(self) -> tuple[float, ...]:
        """Literals found neither in the filing nor in the question.

        This is the README's headline definition (7.6% of train). A question
        counts when any one of its ungrounded literals is also absent from the
        question text.
        """
        missing = self.ungrounded
        if not missing:
            return ()
        asked = self.question_numbers
        if any(v in asked for v in missing):
            return ()
        return missing

    @property
    def steps_count(self) -> int:
        return len(steps(self.program))

    @property
    def answer_is_in_the_table(self) -> bool:
        """Whether the answer could be read off rather than computed."""
        value = as_number(str(self.answer))
        if value is None:
            return False
        return round(value, 6) in self.numbers


def data_dir() -> Path:
    """Where FinQA lives: `$LEDGERTRUTH_DATA` if set, else `<repo>/data`."""
    override = os.environ.get(DATA_ENV, "").strip()
    return Path(override).expanduser() if override else DATA


def available(split: str = "train") -> bool:
    """Whether a split's JSON is on disk in `data_dir()`."""
    return (data_dir() / f"{split}.json").is_file()


def load(split: str = "train") -> tuple[Question, ...]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; have {SPLITS}")
    path = data_dir() / f"{split}.json"
    if not path.is_file():
        raise CorpusMissingError(
            f"{path} is missing. Run scripts/fetch_data.py, which pulls FinQA "
            f"from the authors' repository (set {DATA_ENV} to use another directory)."
        )
    return _load(str(path.resolve()))


@lru_cache(maxsize=4)
def _load(path_text: str) -> tuple[Question, ...]:
    path = Path(path_text)
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusMissingError(
            f"{path} is not valid JSON ({exc}); it is probably a partial download. "
            "Delete it and run scripts/fetch_data.py again."
        ) from exc
    return tuple(
        Question(
            id=row["id"],
            question=row["qa"]["question"],
            program=row["qa"].get("program", ""),
            answer=row["qa"].get("exe_ans"),
            table=tuple(tuple(cell for cell in r) for r in row.get("table", [])),
            pre_text=tuple(row.get("pre_text", [])),
            post_text=tuple(row.get("post_text", [])),
        )
        for row in rows
    )
