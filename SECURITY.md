# Security Policy

## Supported versions

This project is published on PyPI (https://pypi.org/project/aei-history-contract/).
Only the latest published version and the latest commit on `main` are
supported.

| Version | Supported |
|---|---|
| 0.2.x | Yes, best-effort |
| < 0.2.0 | No |

## Reporting a vulnerability

**Please do not open a public GitHub issue for a suspected security
vulnerability.**

Report vulnerabilities privately using GitHub's private vulnerability
reporting (Security tab -> "Report a vulnerability") on the repository,
which opens a private advisory visible only to maintainers. If that
channel is unavailable, contact the maintainers through a private channel
and avoid including exploit details in any public forum.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce, or a minimal proof of concept
- The affected version(s)

## What to expect

- We will acknowledge receipt as soon as reasonably possible.
- We do not commit to a specific response-time or fix-time service level
  agreement (SLA). This is a small, community-maintained-scale project,
  not a commercially supported product.
- We will credit reporters who wish to be credited, once a fix is
  released.

## Scope

## Scope

Pure functions on plain values (Python reference and JavaScript port): no I/O, no network, no clock, no environment variables, no code
run from inputs. Both ports must give the same answer on every golden case. Each control below is covered by tests.

| Boundary | Control | Where | Tests |
|---|---|---|---|
| Records from storage or import | `validate_record`: required fields, unknown fields refused, UTC timestamps, string length caps (source 120, entity_id / label / reason 200), finite numbers only, enumerated metric / kind / entity type | `core.validate_record` (+ JS `validateRecord`) | `test_python.py`, golden cases |
| Unbounded growth | `prune`: retention window plus row (20,000) and byte (5 MB) caps | `core.prune` | `test_python.py`, golden cases |
| CSV opened in a spreadsheet | Text cells starting with `=` `+` `-` `@` (or tab/CR) get a leading apostrophe; RFC 4180 quoting | `core.csv_cell` | `test_python.py`, golden cases |
| Export file name | No path separator can appear: `entity_id` and `now_ts` are both reduced to a safe character set | `core.csv_filename` | `test_python.py`, golden cases |

`prune` and `summarize_changes` expect records that passed `validate_record`; callers must validate data from outside first.
