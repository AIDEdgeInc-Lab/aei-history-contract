"""Writes fixtures/golden.json: inputs for every public function, with `expected` produced by the Python reference and REVIEWED BY HAND
(tests/test_python.py also pins the key behaviours independently of this file). Both ports must reproduce `expected` exactly.
Run from the repo root: PYTHONPATH=src python fixtures/build_golden.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import aei_history_contract as c  # noqa: E402


def rec(ts, value, metric="rain_rate", kind="model", source="open-meteo", entity="A", unit=None, **extra):
    u = unit or {"rain_rate": "mm/h", "temperature": "degC", "wind_speed": "km/h", "status": "enum", "exposure_ratio": "ratio"}.get(metric, "mm/h")
    r = {"ts": ts, "source": source, "entity_id": entity, "metric": metric, "value": value, "unit": u, "kind": kind, "data_version": "aei-mw-exposure 0.2.0"}
    r.update(extra)
    return r


H = lambda h, m=0: "2026-11-02T%02d:%02d:00Z" % (h, m)   # noqa: E731
NOW = "2026-11-02T19:00:00Z"
cases = []
add = lambda fn, args, name: cases.append({"name": name, "fn": fn, "args": args})   # noqa: E731

for s in ["1970-01-01T00:00:00Z", "2000-02-29T23:59:59Z", "2026-11-02T14:00:00Z", "2026-03-01T00:00:00Z", "1969-12-31T23:59:59Z", "2026-11-02T14:00:00.250Z", "2026-02-30T00:00:00", "2026-13-01T00:00:00Z", "not a time"]:
    add("parse_ts", [s], "parse " + s)
for sec in [0, 951868799, 1793628000, 1772323200, -1]:
    add("format_ts", [sec], "format %d" % sec)
for x, d in [(0.25, 1), (0.05, 1), (-0.04, 1), (2.675, 2), (1.005, 2), (0.15, 1), (1234.5678, 2), (-1.25, 1), (0, 2)]:
    add("format_fixed", [x, d], "fixed %r/%d" % (x, d))
    add("round_half_away", [x, d], "round %r/%d" % (x, d))
for x in [0, 1.2, -0.0000001, 1e-7, 3, 1234567.891234567, -2.5, 0.1 + 0.2]:
    add("format_number", [x], "number %r" % x)

good = rec(H(14), 1.2, fetched_ts=H(14, 3), entity_type="site", derived=False)
add("validate_record", [good], "valid full")
add("validate_record", [rec(H(14), None, nodata_reason="rain missing")], "valid null value")
add("validate_record", [rec(H(14), "CLEAR", metric="status", unit="enum")], "valid status string")
add("validate_record", [rec(H(14), "heavy")], "numeric metric with string")
add("validate_record", [dict(good, extra=1)], "unknown field")
add("validate_record", [{k: v for k, v in good.items() if k != "unit"}], "missing unit")
add("validate_record", [rec("2026-11-02 14:00", 1)], "bad ts")
add("validate_record", [rec(H(14), float("inf"))], "infinite value")
add("validate_record", [rec(H(14), 1, kind="prediction")], "bad kind")
add("validate_record", [rec(H(14), 1, metric="rainfall")], "bad metric")
add("validate_record", [rec(H(14), True)], "boolean value")

# prune: retention, row cap, byte cap, future rows kept
rows = [rec("2026-11-01T18:00:00Z", 0.0), rec("2026-11-01T19:00:00Z", 0.5), rec(H(10), 1.0), rec(H(15), 2.0), rec(H(19), 3.0), rec("2026-11-03T02:00:00Z", 4.0, kind="forecast")]
add("prune", [rows, NOW, 24, 20000, 5242880], "retention 24 h keeps the boundary row and a future forecast")
add("prune", [rows, NOW, 6, 20000, 5242880], "retention 6 h")
add("prune", [rows, NOW, 24, 3, 5242880], "row cap 3 drops the oldest")
add("prune", [rows, NOW, 24, 20000, 160], "byte cap drops the oldest")
add("approx_bytes", [rec(H(14), 1.2, source="open-méteo")], "bytes with a non-ASCII source")

# summarize: like-with-like, tolerance, no_data, status, insufficient, kinds kept apart, precision
hist = [
    rec(H(14), 0.0), rec(H(17), 0.62), rec(H(19), 1.24),
    rec(H(14), 0.3, kind="observed", source="eccc-swob"), rec(H(19), 0.3, kind="observed", source="eccc-swob"),
    rec(H(14), 10.04, metric="temperature", unit="degC"), rec(H(19), 10.05, metric="temperature", unit="degC"),
    rec(H(14), "CLEAR", metric="status", unit="enum", derived=True), rec(H(19), "WATCH", metric="status", unit="enum", derived=True),
    rec(H(14), 0.5, metric="exposure_ratio", unit="ratio"), rec(H(19), None, metric="exposure_ratio", unit="ratio", nodata_reason="no rain value"),
    rec(H(18), 5.0, metric="wind_speed", unit="km/h"), rec(H(19), 6.0, metric="wind_speed", unit="km/h"),
    rec(H(14), 1.0, entity="B"),
]
add("summarize_changes", [hist, "A", NOW, 5], "A, 5 h")
add("summarize_changes", [hist, "A", NOW, 1], "A, 1 h (wind only has a 1 h partner; others fall outside 30 min)")
add("summarize_changes", [hist, "A", NOW, 24], "A, 24 h (nothing that old)")
add("summarize_changes", [hist, "B", NOW, 5], "B has a single row")
add("summarize_changes", [hist, "Z", NOW, 5], "unknown entity")
add("summarize_changes", [hist, "A", "2026-11-02T16:00:00Z", 2], "now in the past ignores later rows")
add("summarize_changes", [[rec(H(10), 2.0), rec(H(10, 20), 2.0), rec(H(19), 2.04)], "A", NOW, 9], "tolerance 25 % of 9 h = 135 min")
add("summarize_changes", [[rec(H(17), 1.0, kind="model"), rec(H(19), 3.0, kind="forecast")], "A", NOW, 2], "model and forecast are never compared")
add("summarize_changes", [[rec(H(14), 1.25), rec(H(19), 1.35)], "A", NOW, 5], "1.25 -> 1.35 displayed 1.3 -> 1.4 (half away from zero)")
add("summarize_changes", [[rec(H(14), 1.0, metric="weather_code", unit="wmo_code"), rec(H(19), 61, metric="weather_code", unit="wmo_code")], "A", NOW, 5], "weather code is an enum")

summary = c.summarize_changes(hist, "A", NOW, 5)
for ch in summary["changes"]:
    add("render_text", [ch, 5, "Site A"], "text %s/%s/%s %s" % (ch["metric"], ch["kind"], ch["source"], ch["result"]))
add("render_text", [c.summarize_changes(hist, "A", NOW, 24)["changes"][0], 24, "Site A"], "text insufficient history")
off = [rec(H(14, 24), 0.0), rec(H(19), 1.2)]                       # nearest stored row is 4.6 h earlier than the 5 h asked for
add("render_text", [c.summarize_changes(off, "A", NOW, 5)["changes"][0], 5, "Site A"], "text states the real age (4.6 h), not the window")
off_nd = [rec(H(14, 24), None, nodata_reason="rain missing"), rec(H(19), 1.2)]
add("render_text", [c.summarize_changes(off_nd, "A", NOW, 5)["changes"][0], 5, "Site A"], "text no data states the real age")
add("csv_cell", ["=SUM(A1)"], "cell formula text")
add("csv_cell", [-1.5], "cell negative number is not guarded")
add("csv_cell", ['say "hi", ok'], "cell quoting")
add("csv_cell", [None], "cell null")
add("csv_cell", [True], "cell bool")
add("to_csv", [[good, rec(H(15), None, nodata_reason="x,y"), rec(H(16), -0.5, source="=evil")]], "csv")
add("to_csv", [[]], "csv empty")
add("csv_filename", ["link/009 A→B", "2026-11-02T19:00:00Z"], "filename")
add("csv_filename", ["###", "2026-11-02T19:00:00Z"], "filename fallback")

out = []
for case in cases:
    r = getattr(c, case["fn"])(*case["args"])
    if case["fn"] == "prune":
        r = list(r)
    case["expected"] = r
    out.append(case)
text = json.dumps({"version": c.VERSION, "cases": out}, indent=1, ensure_ascii=False, sort_keys=True).replace("Infinity", "1e999")   # valid JSON in both languages
Path(__file__).with_name("golden.json").write_text(text + "\n", encoding="utf-8")
print(len(out), "cases")
