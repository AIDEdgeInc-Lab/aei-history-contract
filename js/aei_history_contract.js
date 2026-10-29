// JavaScript port of the Velorona local-history contract. Reference: src/aei_history_contract/core.py. Same arithmetic, same answers on every
// case in fixtures/golden.json (tests/test_parity.py). A classic script: in a browser it defines window.VeloronaHistoryContract; in Node it is
// module.exports. No I/O, no clock: callers pass `now`.
(function (root) {
  "use strict";
  const VERSION = "0.2.0";
  const METRICS = ["rain_rate", "temperature", "wind_speed", "snowfall", "weather_code", "rain_attenuation_estimate", "exposure_ratio", "status", "clearance_ratio"];
  const KINDS = ["observed", "forecast", "model"];
  const ENTITY_TYPES = ["link", "site"];
  const CSV_COLUMNS = ["ts", "fetched_ts", "source", "entity_id", "entity_type", "metric", "value", "unit", "kind", "derived", "data_version", "nodata_reason"];
  const REQUIRED = ["ts", "source", "entity_id", "metric", "value", "unit", "kind", "data_version"];
  const PRECISION = { rain_rate: 1, temperature: 1, wind_speed: 1, snowfall: 1, rain_attenuation_estimate: 1, exposure_ratio: 2, clearance_ratio: 2 };
  const ENUM_METRICS = ["status", "weather_code"];
  const LABELS = { rain_rate: "Rain rate", temperature: "Temperature", wind_speed: "Wind speed", snowfall: "Snowfall", weather_code: "Weather code",
    rain_attenuation_estimate: "Rain attenuation estimate", exposure_ratio: "Exposure ratio", status: "Status", clearance_ratio: "Clearance ratio" };
  const KIND_WORDS = { observed: "observed", model: "model-derived", forecast: "forecast" };
  const MIN_TOLERANCE_S = 30 * 60;
  const TS = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?Z$/;
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const isNumber = (v) => typeof v === "number" && Number.isFinite(v);
  const fdiv = (a, b) => Math.floor(a / b);

  function parseTs(s) {
    const m = typeof s === "string" ? TS.exec(s) : null;
    if (!m) return null;
    const y = +m[1], mo = +m[2], d = +m[3], h = +m[4], mi = +m[5], se = +m[6];
    if (!(mo >= 1 && mo <= 12 && d >= 1 && d <= 31 && h <= 23 && mi <= 59 && se <= 59)) return null;
    const ms = +((m[7] || "0").padEnd(3, "0"));
    const yy = y - (mo <= 2 ? 1 : 0), era = fdiv(yy, 400), yoe = yy - era * 400;
    const doy = fdiv(153 * (mo + (mo > 2 ? -3 : 9)) + 2, 5) + d - 1;
    const doe = yoe * 365 + fdiv(yoe, 4) - fdiv(yoe, 100) + doy;
    return (era * 146097 + doe - 719468) * 86400 + h * 3600 + mi * 60 + se + ms / 1000;
  }
  const pad = (n, w) => String(n).padStart(w, "0");
  function formatTs(sec) {
    sec = Math.floor(sec);
    const days = fdiv(sec, 86400), rem = sec - days * 86400, z = days + 719468;
    const era = fdiv(z, 146097), doe = z - era * 146097;
    const yoe = fdiv(doe - fdiv(doe, 1460) + fdiv(doe, 36524) - fdiv(doe, 146096), 365);
    let y = yoe + era * 400;
    const doy = doe - (365 * yoe + fdiv(yoe, 4) - fdiv(yoe, 100)), mp = fdiv(5 * doy + 2, 153);
    const d = doy - fdiv(153 * mp + 2, 5) + 1, m = mp + (mp < 10 ? 3 : -9);
    if (m <= 2) y += 1;
    return `${pad(y, 4)}-${pad(m, 2)}-${pad(d, 2)}T${pad(fdiv(rem, 3600), 2)}:${pad(fdiv(rem % 3600, 60), 2)}:${pad(rem % 60, 2)}Z`;
  }
  function roundHalfAway(x, digits) { const f = 10 ** digits, r = Math.floor(Math.abs(x) * f + 0.5) / f; return x < 0 && r !== 0 ? -r : r; }
  function formatFixed(x, digits) {
    const f = 10 ** digits, n = Math.floor(Math.abs(x) * f + 0.5), neg = x < 0 && n !== 0;
    let s = String(n);
    if (digits) { s = s.padStart(digits + 1, "0"); s = s.slice(0, -digits) + "." + s.slice(-digits); }
    return (neg ? "-" : "") + s;
  }
  function formatNumber(x) {
    let s = formatFixed(x, 6);
    if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
    return s === "-0" || s === "" ? "0" : s;
  }
  const utf8Len = (s) => { let n = 0; for (const ch of s) { const c = ch.codePointAt(0); n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4; } return n; };
  function text(v) { if (v === null || v === undefined) return ""; if (typeof v === "boolean") return v ? "true" : "false"; if (isNumber(v)) return formatNumber(v); return String(v); }
  function approxBytes(r) { return CSV_COLUMNS.reduce((n, c) => n + utf8Len(text(r[c])) + 1, 0); }

  function validateRecord(r) {
    if (!r || typeof r !== "object" || Array.isArray(r)) return ["record must be an object"];
    const errs = [];
    for (const k of REQUIRED) if (!has(r, k)) errs.push("missing " + k);
    for (const k of Object.keys(r)) if (!CSV_COLUMNS.includes(k)) errs.push("unknown field " + k);
    if (errs.length) return errs;
    if (parseTs(r.ts) === null) errs.push("ts must be a UTC ISO-8601 timestamp ending in Z");
    if (has(r, "fetched_ts") && parseTs(r.fetched_ts) === null) errs.push("fetched_ts must be a UTC ISO-8601 timestamp ending in Z");
    for (const [k, mx] of [["source", 120], ["entity_id", 200]]) if (typeof r[k] !== "string" || r[k].length < 1 || [...r[k]].length > mx) errs.push(`${k} must be a string of 1..${mx} characters`);
    for (const k of ["unit", "data_version"]) if (typeof r[k] !== "string" || !r[k]) errs.push(k + " must be a non-empty string");
    if (!METRICS.includes(r.metric)) errs.push("unknown metric");
    if (!KINDS.includes(r.kind)) errs.push("unknown kind");
    if (!ENTITY_TYPES.includes(has(r, "entity_type") ? r.entity_type : "site")) errs.push("unknown entity_type");
    const v = r.value;
    if (v !== null && typeof v !== "string" && !isNumber(v)) errs.push("value must be a finite number, a string or null");
    if (!ENUM_METRICS.includes(r.metric) && typeof v === "string") errs.push("value of a numeric metric must be a number or null");
    if (has(r, "derived") && typeof r.derived !== "boolean") errs.push("derived must be a boolean");
    if (has(r, "nodata_reason") && (typeof r.nodata_reason !== "string" || [...r.nodata_reason].length > 200)) errs.push("nodata_reason must be a string of at most 200 characters");
    return errs;
  }
  const recordKey = (r) => [r.entity_id, r.metric, r.kind, r.source, r.ts];
  const cmpKey = (a, b) => { const x = recordKey(a), y = recordKey(b); for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1; return 0; };

  function prune(records, nowTs, retentionHours = 24, maxRows = 20000, maxBytes = 5 * 1024 * 1024) {
    const cutoff = parseTs(nowTs) - retentionHours * 3600;
    const keep = records.filter((r) => parseTs(r.ts) >= cutoff);
    keep.sort((a, b) => (parseTs(a.ts) - parseTs(b.ts)) || cmpKey(a, b));
    let total = keep.reduce((n, r) => n + approxBytes(r), 0), start = 0;
    while (start < keep.length && (keep.length - start > maxRows || total > maxBytes)) { total -= approxBytes(keep[start]); start++; }
    const kept = keep.slice(start);
    return [kept, records.length - kept.length];
  }

  function summarizeChanges(records, entityId, nowTs, nHours) {
    const now = parseTs(nowTs), target = now - nHours * 3600, tol = Math.max(MIN_TOLERANCE_S, 0.25 * nHours * 3600);
    const groups = new Map();
    for (const r of records) { if (r.entity_id !== entityId) continue; const k = JSON.stringify([r.metric, r.kind, r.source]); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); }
    const keys = [...groups.keys()].map((k) => JSON.parse(k)).sort((a, b) => { for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1; return 0; });
    const changes = [];
    for (const [metric, kind, source] of keys) {
      const rows = groups.get(JSON.stringify([metric, kind, source])).slice().sort((a, b) => parseTs(a.ts) - parseTs(b.ts));
      const upto = rows.filter((r) => parseTs(r.ts) <= now);
      if (!upto.length) continue;
      const cur = upto[upto.length - 1];
      let best = null;
      for (const r of upto) {
        if (r === cur) continue;
        const d = Math.abs(parseTs(r.ts) - target);
        if (d <= tol && (best === null || d < best[0] || (d === best[0] && parseTs(r.ts) > parseTs(best[1].ts)))) best = [d, r];
      }
      const item = { metric, kind, source, unit: cur.unit, now: cur.value, now_ts_actual: cur.ts };
      if (best === null) {
        item.then = null; item.result = "insufficient_history"; item.available_hours = roundHalfAway((parseTs(cur.ts) - parseTs(rows[0].ts)) / 3600, 1);
        changes.push(item); continue;
      }
      const then = best[1];
      item.then = then.value; item.then_ts_actual = then.ts;
      const a = then.value, b = cur.value;
      if (a === null || b === null) {
        item.result = "no_data";
        const reason = (b === null ? cur : then).nodata_reason;
        if (reason) item.nodata_reason = reason;
        item.delta = null;
      } else if (ENUM_METRICS.includes(metric) || !(isNumber(a) && isNumber(b))) {
        item.result = a === b ? "unchanged" : "status_changed"; item.delta = null;
      } else {
        const dg = PRECISION[metric], ra = roundHalfAway(a, dg), rb = roundHalfAway(b, dg);
        item.delta = roundHalfAway(rb - ra, dg);
        item.result = ra === rb ? "unchanged" : rb > ra ? "increased" : "decreased";
      }
      changes.push(item);
    }
    return { entity_id: entityId, now_ts: nowTs, then_ts: formatTs(target), n_hours: nHours, changes };
  }

  const hhmm = (ts) => ts.slice(11, 16) + " UTC";
  const gapHours = (change) => roundHalfAway((parseTs(change.now_ts_actual) - parseTs(change.then_ts_actual)) / 3600, 1);
  function renderText(change, nHours, entityLabel) {
    const who = `${LABELS[change.metric]} at ${entityLabel}`, hrs = formatNumber(nHours), how = `${KIND_WORDS[change.kind]}, ${change.source}`;
    const ago = change.then_ts_actual ? formatNumber(gapHours(change)) : hrs;   // the real age of the compared value, not the requested window
    if (change.result === "insufficient_history") return `${who}: no stored value from about ${hrs} h ago (this series covers ${formatNumber(change.available_hours)} h).`;
    if (change.result === "no_data") return `${who}: NO DATA ${change.now === null ? "now" : ago + " h ago"}${change.nodata_reason ? " (" + change.nodata_reason + ")" : ""}. Nothing was substituted.`;
    const dg = PRECISION[change.metric];
    const fmt = dg !== undefined && isNumber(change.now) ? (v) => formatFixed(v, dg) : (v) => String(v);
    const unit = change.unit === "enum" || change.unit === "wmo_code" ? "" : " " + change.unit;
    return `${who}: ${fmt(change.now)}${unit} now, ${fmt(change.then)}${unit} ${ago} h ago (${how}, ${hhmm(change.then_ts_actual)} → ${hhmm(change.now_ts_actual)}).`;
  }

  function csvCell(v) {
    if (typeof v === "string" && v && "=+-@\t\r".includes(v[0])) v = "'" + v;
    const s = text(v);
    return /[,"\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function toCsv(records) {
    const lines = [CSV_COLUMNS.join(",")];
    for (const r of records) lines.push(CSV_COLUMNS.map((c) => csvCell(has(r, c) ? r[c] : null)).join(","));
    return lines.join("\n") + "\n";
  }
  function csvFilename(entityId, nowTs) {
    const safe = entityId.replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 60).replace(/^_+|_+$/g, "") || "history";
    return `velorona-history-${safe}-${nowTs.replace(/:/g, "").replace(/-/g, "")}.csv`;
  }

  const api = { VERSION, METRICS, KINDS, CSV_COLUMNS, PRECISION, LABELS, parseTs, formatTs, roundHalfAway, formatFixed, formatNumber, validateRecord, recordKey, approxBytes, prune, summarizeChanges, renderText, csvCell, toCsv, csvFilename };
  if (typeof module === "object" && module.exports) module.exports = api; else root.VeloronaHistoryContract = api;
})(typeof window !== "undefined" ? window : globalThis);
