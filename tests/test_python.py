"""Independent pins of the rules in CONTRACT.md section 2 (not derived from golden.json) plus the golden cases against the Python reference."""
import copy
import json
from pathlib import Path

import pytest

import aei_history_contract as c

GOLD = json.loads((Path(__file__).resolve().parent.parent / "fixtures" / "golden.json").read_text(encoding="utf-8"))


def rec(ts, v, metric="rain_rate", kind="model", source="open-meteo", entity="A", unit="mm/h"):
    return {"ts": ts, "source": source, "entity_id": entity, "metric": metric, "value": v, "unit": unit, "kind": kind, "data_version": "t"}


@pytest.mark.parametrize("case", GOLD["cases"], ids=lambda x: x["name"])
def test_golden_case(case):
    out = getattr(c, case["fn"])(*copy.deepcopy(case["args"]))
    assert json.loads(json.dumps(out)) == case["expected"]


def test_version_matches_pyproject_and_golden():
    assert c.VERSION == GOLD["version"] == "0.2.1"
    assert 'version = "0.2.1"' in (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()


def test_the_contract_example_sentence():
    rows = [rec("2026-11-02T14:00:00Z", 0.0), rec("2026-11-02T19:00:00Z", 1.2)]
    ch = c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]
    assert c.render_text(ch, 5, "Site A") == "Rain rate at Site A: 1.2 mm/h now, 0.0 mm/h 5 h ago (model-derived, open-meteo, 14:00 UTC → 19:00 UTC)."


def test_never_compares_across_kind_or_source():
    rows = [rec("2026-11-02T14:00:00Z", 9.0, kind="observed", source="eccc-swob"), rec("2026-11-02T19:00:00Z", 1.0, kind="model")]
    ch = c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"]
    assert {x["result"] for x in ch} == {"insufficient_history"}


def test_null_is_no_data_never_zero():
    rows = [rec("2026-11-02T14:00:00Z", 0.0), rec("2026-11-02T19:00:00Z", None)]
    ch = c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]
    assert ch["result"] == "no_data" and ch["now"] is None and ch["delta"] is None


def test_unchanged_is_decided_at_display_precision():
    rows = [rec("2026-11-02T14:00:00Z", 1.21), rec("2026-11-02T19:00:00Z", 1.24)]
    assert c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]["result"] == "unchanged"


def test_tolerance_is_the_larger_of_30_min_and_25_percent():
    rows = [rec("2026-11-02T13:31:00Z", 1.0), rec("2026-11-02T19:00:00Z", 2.0)]   # target 14:00, 29 min away
    assert c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]["result"] == "increased"
    rows = [rec("2026-11-02T13:29:00Z", 1.0), rec("2026-11-02T19:00:00Z", 2.0)]   # 31 min away, 25 % of 5 h = 75 min -> accepted
    assert c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]["result"] == "increased"
    rows = [rec("2026-11-02T12:00:00Z", 1.0), rec("2026-11-02T19:00:00Z", 2.0)]   # 2 h away, beyond 75 min
    assert c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]["result"] == "insufficient_history"


def test_text_never_uses_judgement_words():
    for case in GOLD["cases"]:
        if case["fn"] == "render_text":
            low = case["expected"].lower()
            assert not any(w in low for w in ("worsen", "improv", "predict", "forecast to"))


def test_entity_label_is_an_optional_column_next_to_the_hashed_id():
    r = {"ts": "2026-11-02T14:00:00Z", "source": "s", "entity_id": "abc123", "entity_label": "Site, A", "metric": "rain_rate", "value": 1, "unit": "mm/h", "kind": "model", "data_version": "v"}
    assert c.validate_record(r) == [] and c.validate_record(dict(r, entity_label="x" * 201)) and c.validate_record(dict(r, entity_label=3))
    head, line = c.to_csv([r]).splitlines()
    assert head.split(",")[3:5] == ["entity_id", "entity_label"] and line.startswith('2026-11-02T14:00:00Z,,s,abc123,"Site, A",')
    assert c.summarize_changes([r], "abc123", "2026-11-02T14:00:00Z", 6)   # the label never takes part in matching


def test_csv_guards_formulas_in_text_but_not_numbers():
    assert c.csv_cell("=1+1") == "'=1+1" and c.csv_cell(-1.5) == "-1.5" and c.csv_cell("a,b") == '"a,b"'


def test_prune_never_returns_more_than_the_caps():
    rows = [rec("2026-11-02T%02d:%02d:00Z" % (h, m), 1.0) for h in range(0, 19) for m in (0, 30)]
    kept, dropped = c.prune(rows, "2026-11-02T19:00:00Z", 24, 10, 10**9)
    assert len(kept) == 10 and dropped == len(rows) - 10 and kept[-1]["ts"] == "2026-11-02T18:30:00Z"


def test_the_text_states_the_real_age_of_the_compared_value_not_the_requested_window():
    rows = [rec("2026-11-02T14:24:00Z", 0.0), rec("2026-11-02T19:00:00Z", 1.2)]       # nearest stored row is 4 h 36 min earlier; the window asked for 5 h
    ch = c.summarize_changes(rows, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]
    assert ch["result"] == "increased"
    assert c.render_text(ch, 5, "Site A") == "Rain rate at Site A: 1.2 mm/h now, 0.0 mm/h 4.6 h ago (model-derived, open-meteo, 14:24 UTC → 19:00 UTC)."
    nodata = [dict(rec("2026-11-02T14:24:00Z", None), nodata_reason="rain missing"), rec("2026-11-02T19:00:00Z", 1.2)]
    ch = c.summarize_changes(nodata, "A", "2026-11-02T19:00:00Z", 5)["changes"][0]
    assert "NO DATA 4.6 h ago (rain missing)" in c.render_text(ch, 5, "Site A")


def test_csv_filename_never_contains_a_path_separator():
    """Security baseline (0.2.1): now_ts is sanitized like entity_id, so a caller that joins the name onto a folder cannot be sent
    elsewhere. Valid timestamps give the same name as before (pinned by the golden cases)."""
    for entity, now in [("a/b", "../../etc/passwd"), ("..", "..\\..\\x"), ("A", "2026-11-02T19:00:00Z/../../x"), ("A", "x\x00y")]:
        name = c.csv_filename(entity, now)
        assert "/" not in name and "\\" not in name and "\x00" not in name
        assert name.startswith("velorona-history-") and name.endswith(".csv")
