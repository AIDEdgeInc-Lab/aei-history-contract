# aei-history-contract

The shared contract for Velorona's **local history** (data a customer keeps on their own machine; Velorona stores none of it):

- `schemas/` — `HistoryRecord` and `ChangeSummary` JSON Schemas (draft 2020-12).
- `src/aei_history_contract/core.py` — the Python **reference**: record validation, retention and size-cap pruning, the deterministic "what changed" rules, sentence rendering, CSV export.
- `js/aei_history_contract.js` — the JavaScript **port** (a classic script; `window.VeloronaHistoryContract` in a browser, `module.exports` in Node).
- `fixtures/golden.json` — inputs and expected outputs for every public function. Both ports must reproduce it exactly (`tests/`).

Rules in one place: values are compared only with the same entity, metric, `kind` and `source`; `then` is the stored row nearest to `now − n hours` within max(30 min, 25 % of n); "unchanged" means equal at the displayed precision; a missing value is `no_data`, never 0; text is built from fields only ("Rain rate at Site A: 1.2 mm/h now, 0.0 mm/h 5 h ago (model-derived, open-meteo, 14:00 UTC → 19:00 UTC)."), with no words like "worsening" and no forecasts of our own.

No I/O, no clock, no dependencies. Storage (IndexedDB in the Map, SQLite in the QGIS plugin) and capture hooks belong to each product.

Tests: `PYTHONPATH=src python -m pytest tests` (runs the JS port too; needs Node 18+). Regenerate fixtures only deliberately: `PYTHONPATH=src python fixtures/build_golden.py`, then review the diff.

Release discipline: any change to behaviour or schema = version bump in `pyproject.toml`, `core.py`, `js/aei_history_contract.js` (a test checks they agree), a CHANGELOG entry, and the owner's release approval before a product pins it.
