# Changelog

## 0.2.0 (PROPOSED by the QGIS plugin work, 2026-10-29; not approved, not released)
`render_text` states the real age of the compared value (hours between `then_ts_actual` and `now_ts_actual`, one decimal) instead of the requested window.
With `then` accepted up to 25 % of the window away, "0.0 mm/h 6 h ago" could describe a value 4.6 h old; the times in the brackets showed it but the sentence
did not. Identical output whenever the compared row is exactly n hours earlier (the 0.1.0 example sentence is unchanged). Python + JS + 2 new golden cases.
Products that pin `>=0.1.0,<0.2` must widen the pin when they adopt it.

## 0.1.0 (unreleased, awaiting owner approval)
First version: HistoryRecord / ChangeSummary schemas, Python reference, JS port, 82 golden cases. Not published; no product pins it yet.
