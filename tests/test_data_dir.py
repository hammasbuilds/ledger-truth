"""The data directory override and failure modes, without FinQA on disk."""

from __future__ import annotations

import json

import pytest

from ledgertruth import corpus
from ledgertruth.__main__ import main

ROW = {
    "id": "X/2020/page_1.pdf-1",
    "qa": {"question": "what was the change from 5735 to 5829?",
           "program": "subtract(5829, 5735)", "exe_ans": 94.0},
    "table": [["", "2020", "2019"], ["revenue", "$ 5829", "$ 5735"]],
    "pre_text": ["margin was 12.5% in 2020"],
    "post_text": [],
}


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv(corpus.DATA_ENV, str(tmp_path))
    return tmp_path


def test_env_var_overrides_the_directory(data):
    assert corpus.data_dir() == data
    assert not corpus.available("train")


def test_missing_split_names_the_fetch_script_and_env_var(data):
    with pytest.raises(corpus.CorpusMissingError, match="fetch_data.py.*LEDGERTRUTH_DATA"):
        corpus.load("dev")


def test_truncated_json_is_reported_as_a_partial_download(data):
    (data / "dev.json").write_text('[{"id": "a"', encoding="utf-8")
    with pytest.raises(corpus.CorpusMissingError, match="partial download"):
        corpus.load("dev")


def test_loads_from_the_override(data):
    unsourced = dict(ROW, id="Y/2020/page_2.pdf-1",
                     qa={"question": "growth?", "program": "divide(5829, 23.6%)",
                         "exe_ans": 24699.15})
    stated = dict(ROW, id="Z/2020/page_3.pdf-1",
                  qa={"question": "if the rate was 7% what is the cost?",
                      "program": "multiply(5829, 7%)", "exe_ans": 408.03})
    (data / "test.json").write_text(json.dumps([ROW, unsourced, stated]), encoding="utf-8")
    qs = corpus.load("test")
    assert [q.ungrounded for q in qs] == [(), (0.236,), (0.07,)]
    assert [q.unsourceable for q in qs] == [(), (0.236,), ()]


def test_cli_unsourceable_json(data, capsys):
    (data / "dev.json").write_text(json.dumps([ROW]), encoding="utf-8")
    assert main(["unsourceable", "--split", "dev", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"split": "dev", "questions": 1, "flagged": 0, "items": []}


def test_cli_without_data_exits_2_with_a_message(data, capsys):
    assert main(["unsourceable", "--split", "train"]) == 2
    assert "fetch_data.py" in capsys.readouterr().err


def test_cli_run(capsys):
    assert main(["run", "divide(9896, 23.6%)"]) == 0
    assert capsys.readouterr().out.strip() == "41932.2"
    assert main(["run", "nonsense", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "bad_program"


def test_cli_run_with_table(tmp_path, capsys):
    table = tmp_path / "t.json"
    table.write_text(json.dumps([["q1", "1", "3"]]), encoding="utf-8")
    assert main(["run", "table_average(q1, none)", "--table", str(table)]) == 0
    assert capsys.readouterr().out.strip() == "2"
    table.write_text('{"a": 1}', encoding="utf-8")
    assert main(["run", "table_average(q1, none)", "--table", str(table)]) == 2
