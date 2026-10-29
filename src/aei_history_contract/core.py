"""Reference implementation of the Velorona local-history contract (HistoryRecord, ChangeSummary rules, CSV export).

Pure functions on plain dicts and strings: no I/O, no clock (callers pass `now`). The JavaScript port in js/aei_history_contract.js must give
the same answer on every case in fixtures/golden.json; tests/test_parity.py runs both. Numbers are rounded half away from zero on a scaled
integer, never with round() or toFixed(), so Python and JavaScript agree on every platform.
"""
import math
import re

VERSION = "0.2.0"
SCHEMA_RECORD = "https://velorona.ai/schemas/history-record/1.json"
SCHEMA_CHANGE = "https://velorona.ai/schemas/change-summary/1.json"

METRICS = ("rain_rate", "temperature", "wind_speed", "snowfall", "weather_code", "rain_attenuation_estimate", "exposure_ratio", "status", "clearance_ratio")
KINDS = ("observed", "forecast", "model")
ENTITY_TYPES = ("link", "site")
CSV_COLUMNS = ("ts", "fetched_ts", "source", "entity_id", "entity_type", "metric", "value", "unit", "kind", "derived", "data_version", "nodata_reason")
REQUIRED = ("ts", "source", "entity_id", "metric", "value", "unit", "kind", "data_version")
# Decimal places at which a value is displayed, hence the precision at which "unchanged" is decided (the shipped QGIS rule: not a physical threshold).
PRECISION = {"rain_rate": 1, "temperature": 1, "wind_speed": 1, "snowfall": 1, "rain_attenuation_estimate": 1, "exposure_ratio": 2, "clearance_ratio": 2}
ENUM_METRICS = ("status", "weather_code")   # compared for equality, never as a number
LABELS = {"rain_rate": "Rain rate", "temperature": "Temperature", "wind_speed": "Wind speed", "snowfall": "Snowfall", "weather_code": "Weather code",
          "rain_attenuation_estimate": "Rain attenuation estimate", "exposure_ratio": "Exposure ratio", "status": "Status", "clearance_ratio": "Clearance ratio"}
KIND_WORDS = {"observed": "observed", "model": "model-derived", "forecast": "forecast"}
MIN_TOLERANCE_S = 30 * 60

_TS = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?Z$")


def parse_ts(s):
    """'2026-11-02T14:00:00Z' -> seconds since 1970-01-01 UTC (float, milliseconds kept). None if it is not a UTC ISO-8601 timestamp."""
    m = _TS.match(s) if isinstance(s, str) else None
    if not m:
        return None
    y, mo, d, h, mi, se = (int(m.group(i)) for i in range(1, 7))
    if not (1 <= mo <= 12 and 1 <= d <= 31 and h <= 23 and mi <= 59 and se <= 59):
        return None
    ms = int((m.group(7) or "0").ljust(3, "0"))
    yy = y - (1 if mo <= 2 else 0)   # days from civil (Howard Hinnant), identical arithmetic in the JS port
    era = yy // 400
    yoe = yy - era * 400
    doy = (153 * (mo + (-3 if mo > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * 146097 + doe - 719468
    return days * 86400 + h * 3600 + mi * 60 + se + ms / 1000


def format_ts(sec):
    """Inverse of parse_ts, whole seconds, always 'Z'."""
    sec = int(math.floor(sec))
    days, rem = divmod(sec, 86400)
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    y += 1 if m <= 2 else 0
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, rem // 3600, (rem % 3600) // 60, rem % 60)


def round_half_away(x, digits):
    """Round to `digits` decimals, halves away from zero, on a scaled integer (same arithmetic as the JS port)."""
    f = 10 ** digits
    r = math.floor(abs(x) * f + 0.5) / f
    return -r if x < 0 and r != 0 else r


def format_fixed(x, digits):
    """Fixed decimals, no exponent, never '-0.0'."""
    f = 10 ** digits
    n = math.floor(abs(x) * f + 0.5)
    neg = x < 0 and n != 0
    s = str(int(n))
    if digits:
        s = s.rjust(digits + 1, "0")
        s = s[:-digits] + "." + s[-digits:]
    return ("-" if neg else "") + s


def format_number(x):
    """Up to 6 decimals, trailing zeros trimmed, no exponent: the CSV and text form of any numeric value."""
    s = format_fixed(x, 6)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_record(r):
    """-> list of problems (empty = valid). Unknown fields are a problem (additionalProperties: false)."""
    if not isinstance(r, dict):
        return ["record must be an object"]
    errs = []
    for k in REQUIRED:
        if k not in r:
            errs.append("missing " + k)
    for k in r:
        if k not in CSV_COLUMNS:
            errs.append("unknown field " + k)
    if errs:
        return errs
    if parse_ts(r["ts"]) is None:
        errs.append("ts must be a UTC ISO-8601 timestamp ending in Z")
    if "fetched_ts" in r and parse_ts(r["fetched_ts"]) is None:
        errs.append("fetched_ts must be a UTC ISO-8601 timestamp ending in Z")
    for k, mx in (("source", 120), ("entity_id", 200)):
        if not isinstance(r[k], str) or not 1 <= len(r[k]) <= mx:
            errs.append(k + " must be a string of 1.." + str(mx) + " characters")
    for k in ("unit", "data_version"):
        if not isinstance(r[k], str) or not r[k]:
            errs.append(k + " must be a non-empty string")
    if r["metric"] not in METRICS:
        errs.append("unknown metric")
    if r["kind"] not in KINDS:
        errs.append("unknown kind")
    if r.get("entity_type", "site") not in ENTITY_TYPES:
        errs.append("unknown entity_type")
    v = r["value"]
    if v is not None and not isinstance(v, str) and not _is_number(v):
        errs.append("value must be a finite number, a string or null")
    if r["metric"] not in ENUM_METRICS and isinstance(v, str):
        errs.append("value of a numeric metric must be a number or null")
    if "derived" in r and not isinstance(r["derived"], bool):
        errs.append("derived must be a boolean")
    if "nodata_reason" in r and (not isinstance(r["nodata_reason"], str) or len(r["nodata_reason"]) > 200):
        errs.append("nodata_reason must be a string of at most 200 characters")
    return errs


def record_key(r):
    return [r["entity_id"], r["metric"], r["kind"], r["source"], r["ts"]]


def _utf8_len(s):
    return len(s.encode("utf-8"))


def approx_bytes(r):
    """Size used for the cap: the UTF-8 length of the record's canonical text (fields in CSV order, '|'-joined). Same in both ports."""
    return sum(_utf8_len(_text(r.get(c))) + 1 for c in CSV_COLUMNS)


def _text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if _is_number(v):
        return format_number(v)
    return str(v)


def prune(records, now_ts, retention_hours=24, max_rows=20000, max_bytes=5 * 1024 * 1024):
    """Keep rows whose ts is within `retention_hours` of now (future rows kept: they are forecasts), then drop the oldest rows
    (by ts, ties by key) until both caps hold. Returns (kept, dropped_count), kept sorted by ts then key."""
    now = parse_ts(now_ts)
    cutoff = now - retention_hours * 3600
    keep = [r for r in records if parse_ts(r["ts"]) >= cutoff]
    keep.sort(key=lambda r: (parse_ts(r["ts"]), record_key(r)))
    total = sum(approx_bytes(r) for r in keep)
    start = 0
    while start < len(keep) and (len(keep) - start > max_rows or total > max_bytes):
        total -= approx_bytes(keep[start])
        start += 1
    kept = keep[start:]
    return kept, len(records) - len(kept)


def _series(records, entity_id):
    out = {}
    for r in records:
        if r["entity_id"] != entity_id:
            continue
        out.setdefault((r["metric"], r["kind"], r["source"]), []).append(r)
    return out


def summarize_changes(records, entity_id, now_ts, n_hours):
    """ChangeSummary for one entity (CONTRACT section 2). Like is compared with like: same metric, kind AND source, never across them.
    now = the newest row at or before now_ts. then = the row nearest to now_ts - n_hours, accepted only within max(30 min, 25 % of n_hours)."""
    now = parse_ts(now_ts)
    target = now - n_hours * 3600
    tol = max(MIN_TOLERANCE_S, 0.25 * n_hours * 3600)
    changes = []
    for (metric, kind, source), rows in sorted(_series(records, entity_id).items()):
        rows = sorted(rows, key=lambda r: parse_ts(r["ts"]))
        upto = [r for r in rows if parse_ts(r["ts"]) <= now]
        if not upto:
            continue
        cur = upto[-1]
        cand = [r for r in upto if r is not cur]
        best = None
        for r in cand:
            d = abs(parse_ts(r["ts"]) - target)
            if d <= tol and (best is None or d < best[0] or (d == best[0] and parse_ts(r["ts"]) > parse_ts(best[1]["ts"]))):
                best = (d, r)
        item = {"metric": metric, "kind": kind, "source": source, "unit": cur["unit"], "now": cur["value"], "now_ts_actual": cur["ts"]}
        if best is None:
            item.update({"then": None, "result": "insufficient_history", "available_hours": round_half_away((parse_ts(cur["ts"]) - parse_ts(rows[0]["ts"])) / 3600, 1)})
            changes.append(item)
            continue
        then = best[1]
        item.update({"then": then["value"], "then_ts_actual": then["ts"]})
        a, b = then["value"], cur["value"]
        if a is None or b is None:
            item["result"] = "no_data"
            reason = (cur if b is None else then).get("nodata_reason")
            if reason:
                item["nodata_reason"] = reason
            item["delta"] = None
        elif metric in ENUM_METRICS or not (_is_number(a) and _is_number(b)):
            item["result"] = "unchanged" if a == b else "status_changed"
            item["delta"] = None
        else:
            dg = PRECISION[metric]
            ra, rb = round_half_away(a, dg), round_half_away(b, dg)
            item["delta"] = round_half_away(rb - ra, dg)
            item["result"] = "unchanged" if ra == rb else ("increased" if rb > ra else "decreased")
        changes.append(item)
    return {"entity_id": entity_id, "now_ts": now_ts, "then_ts": format_ts(target), "n_hours": n_hours, "changes": changes}


def _hhmm(ts):
    return ts[11:16] + " UTC"


def _gap_hours(change):
    """Hours between the two stored rows actually compared, to one decimal (5 for 14:00 -> 19:00; 4.6 when the nearest row was 4 h 36 min earlier)."""
    return round_half_away((parse_ts(change["now_ts_actual"]) - parse_ts(change["then_ts_actual"])) / 3600, 1)


def render_text(change, n_hours, entity_label):
    """One sentence per change, built from fields only (no adjectives, no 'worsening'). `entity_label` is shown, e.g. 'Site A'."""
    label = LABELS[change["metric"]]
    who = f"{label} at {entity_label}"
    hrs = format_number(n_hours)
    ago = format_number(_gap_hours(change)) if change.get("then_ts_actual") else hrs   # the real age of the compared value, not the requested window
    how = f"{KIND_WORDS[change['kind']]}, {change['source']}"
    res = change["result"]
    if res == "insufficient_history":
        return f"{who}: no stored value from about {hrs} h ago (this series covers {format_number(change['available_hours'])} h)."
    if res == "no_data":
        why = change.get("nodata_reason")
        return f"{who}: NO DATA {'now' if change['now'] is None else ago + ' h ago'}{' (' + why + ')' if why else ''}. Nothing was substituted."
    dg = PRECISION.get(change["metric"])
    fmt = (lambda v: format_fixed(v, dg)) if dg is not None and _is_number(change["now"]) else (lambda v: str(v))
    unit = "" if change["unit"] in ("enum", "wmo_code") else " " + change["unit"]
    return (f"{who}: {fmt(change['now'])}{unit} now, {fmt(change['then'])}{unit} {ago} h ago "
            f"({how}, {_hhmm(change['then_ts_actual'])} → {_hhmm(change['now_ts_actual'])}).")


def csv_cell(v):
    """RFC 4180 quoting; a TEXT cell starting with = + - @ (or tab/CR) gets a leading apostrophe so a spreadsheet will not evaluate it.
    Numbers are written as numbers and are not guarded (a negative number is not a formula)."""
    if isinstance(v, str) and v and v[0] in "=+-@\t\r":
        v = "'" + v
    s = _text(v)
    return '"' + s.replace('"', '""') + '"' if any(c in s for c in ',"\n\r') else s


def to_csv(records):
    """Header + one line per record in the given order, columns in schema order, '\\n' line ends, trailing newline."""
    lines = [",".join(CSV_COLUMNS)]
    for r in records:
        lines.append(",".join(csv_cell(r.get(c)) for c in CSV_COLUMNS))
    return "\n".join(lines) + "\n"


def csv_filename(entity_id, now_ts):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", entity_id)[:60].strip("_") or "history"
    return f"velorona-history-{safe}-{now_ts.replace(':', '').replace('-', '')}.csv"
