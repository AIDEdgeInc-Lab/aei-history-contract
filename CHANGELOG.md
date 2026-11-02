# Changelog

## 0.2.0 - 2026-11-02
`render_text` states the real age of the compared value (hours between `then_ts_actual` and `now_ts_actual`, one decimal) instead of the requested window.
With `then` accepted up to 25 % of the window away, "0.0 mm/h 6 h ago" could describe a value 4.6 h old; the times in the brackets showed it but the sentence
did not. Identical output whenever the compared row is exactly n hours earlier (the 0.1.0 example sentence is unchanged). Python + JS + 2 new golden cases.
`entity_label` (new, optional, string up to 200 characters): the display name of the entity, written as a CSV column right after `entity_id`; never used for matching or pruning. CSV header gains the column (13 columns); `approx_bytes` counts it (+1 byte per record when absent). Python + JS + 5 new golden cases (89 total).
Products that pin `>=0.1.0,<0.2` must widen the pin when they adopt it.

## 0.1.0 - first version (never published on its own; part of 0.2.0)
First version: HistoryRecord / ChangeSummary schemas, Python reference, JS port, 82 golden cases. No product pinned it before 0.2.0.
