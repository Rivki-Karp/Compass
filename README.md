# Compass

[![CI](https://github.com/Rivki-Karp/Compass/actions/workflows/ci.yml/badge.svg)](https://github.com/Rivki-Karp/Compass/actions/workflows/ci.yml)

Compass is a Hebrew chat assistant for Strauss Group employees. It answers one question:
*"If I switch company car, go electric, or give up the car, how will my monthly net
salary change?"*

**Core principle:** every number shown to a user comes from deterministic code that reads
versioned data files. The same inputs and the same rules always give the same output. Rules
live in config ([data/rules.yaml](data/rules.yaml)), not in code, so a pilot replaces data
files, not code.

Built for the "קוד פתוח" AI Hackathon 2026 (final: Wed 21/10/2026).

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). These commands work on Windows, macOS and Linux:

```sh
uv run python tasks.py install   # create .venv with Python 3.12 and sync uv.lock
uv run python tasks.py data      # rebuild all generated data from raw/
uv run python tasks.py test      # run the tests
uv run python tasks.py lint      # ruff check + ruff format --check
uv run python tasks.py fmt       # apply formatting
uv run python tasks.py demo E-001  # Hebrew breakdown of a golden employee (E-001 … E-006)
uv run python tasks.py calc      # interactive calculator for your own numbers
uv run python tasks.py serve     # the API on http://127.0.0.1:8000 (Swagger at /docs)
uv run python tasks.py openapi   # regenerate openapi.json after API changes
```

If you have `make`, `make install|data|test|lint|fmt` does the same.

The raw challenge files (public hackathon material, about 20 MB) are committed in `raw/`
byte-for-byte; [raw/README.md](raw/README.md) lists them with their SHA-256.
`tasks.py data` is idempotent: it rebuilds `data/vehicles.db`
atomically and writes byte-identical JSON on every run.

## Project layout

```
compass/
  config.py            paths, resolved relative to the repo root
  rules.py             load_rules(): validated, frozen view of data/rules.yaml
  data/
    drive.py           drive_code -> petrol|hybrid|plugin|electric
    vehicles.py        get_value_of_use(), find_by_codes(), find_by_names()  (vehicles.db)
    catalog.py         load_catalog(), get_car(), cars_for_group()  (catalog.json)
    occupations.py     load_occupations(), get_occupation()         (occupations.json)
  engine/              deterministic net calculation (see "Engine" below)
    models.py          EmployeeProfile, Scenario, NetBreakdown, Comparison, Eligibility, Option
    context.py         build_context(): rules + catalog + occupations, cross-checked
    decimal_math.py    exact() Decimal context; the only display rounding
    tax.py             income tax, National Insurance, health, pension credit
    net.py             compute_net() and the electric gross-up solver
    compare.py         compare(): diff, delta lines, display lines, explanation facts
    eligibility.py     check_eligibility()
    options.py         list_options()
    serialize.py       to_api_dict(): JSON-safe results (exact as strings, display as ints)
  search/              normalize() + fuzzy search: occupations, catalog (+ aliases), Tax Authority
  state/               SQLite session store (data/app.db): sessions, messages, slots, tickets, events
  tools/               the 9 agent tools, their registry and ToolRunner (never raises)
  api/                 FastAPI app: sessions, SSE, dev tools, tickets, data, admin
  reference.py         the 6 golden fixtures as engine inputs (tests + demo)
  demo.py / calc.py    `tasks.py demo E-00X` / `tasks.py calc`
data/
  rules.yaml           business rules: hand-edited, commented, validated on load
  aliases.yaml         how employees name the catalog cars (Hebrew + spellings), curated
  catalog.json         20 company cars                  (generated from the Excel)
  occupations.json     14 occupations                   (generated from the Excel)
  vehicles.db          Tax Authority dataset in SQLite  (generated, git-ignored)
  app.db               session store                    (created on startup, git-ignored)
raw/                   raw challenge inputs, committed byte-for-byte (see raw/README.md)
scripts/
  build_vehicles_db.py raw CSV  -> data/vehicles.db
  extract_excel.py     raw xlsx -> data/*.json + tests/fixtures/reference_*.json
tests/                 pytest suite; fixtures/ holds the 6 golden reference employees
openapi.json           the API schema, committed for frontend type generation
tasks.py               cross-platform task runner (Makefile wraps it)
```

Planned layers, not built yet: `compass/agent/` (the Claude tool-use loop, which plugs into
the tool registry and the `AgentRunner` seam) and `web/` (React). Nothing calls an LLM yet,
and the engine imports none of the layers above it.

## Data sources

| Source | Used for |
|---|---|
| **Israel Tax Authority: "מאגר שווי שימוש ברכב 2026 - הקובץ המורחב"** (extended value-of-use dataset, tax year 2026; 77,988 rows; [gov.il value-of-use page](https://www.gov.il/he/service/itc-mm_usecar10)) | `data/vehicles.db`: official monthly value of use (שווי שימוש) per vehicle |
| Challenge Excel `strauss_challenge_data.xlsx` | catalog, occupations, the 6 reference employees and their expected results |
| Challenge rules `strauss-rules.json` (version `mock-2026-10-12`) | `data/rules.yaml` |

**The challenge data is fictitious.** The only real values are the manufacturer and model
codes and the value of use, which come from the Tax Authority dataset. A test
(`tests/test_catalog_cross_check.py`) proves that all 20 catalog cars exist in the official
dataset with identical values. The tax tables are 2025 values, used for illustration only.

[raw/README.md](raw/README.md) lists each file's original filename, SHA-256 and known
issues.

### Things to know about the Tax Authority dataset

- **`drive_code`: the header disagrees with the data.** The CSV header reads
  `1-חשמלי.2-היברידי.3-פלג-אין`. The data actually follows the rules-file mapping:
  **0 = petrol, 1 = hybrid, 2 = plug-in, 3 = electric** (for example BYD ATTO 3 = 3, Toyota
  YARIS CROSS HSD = 1, Kia PICANTO = 0). We use the rules-file mapping, and a test locks
  it in.
- **Only the full official key identifies a vehicle.** The key is tax year + registration
  year + vehicle type + manufacturer code + model code. Model codes are reused across
  vehicle types. For example, codes `01014`/`00003` (2025) are a private **BYD ATTO 3**
  (value of use 3,130) *and* a commercial **BYD TANG** (6,950). So `find_by_codes()`
  returns every match and never picks one.
- **The commercial name is not a key.** "YARIS CROSS HSD" (2025, private) maps to
  several model codes with different values. A name lookup must return candidates and
  never pick one automatically.
- Codes are zero-padded **strings** (`"00413"` ≠ `413`). Money is `Decimal`, never `float`.

## Engine

`compass/engine/` turns an employee profile and a scenario into an exact monthly net-salary
breakdown, and compares two scenarios. Every number the product shows comes from here. All
rule values come from `data/rules.yaml`, the catalog and the occupations; the engine has no
rule constants of its own.

### The formula (one scenario)

```
cash_income        = base_salary + commissions + bonus             # contributions base "gross"
taxable_income     = cash_income + value_of_use + maintenance + electric_gross
income_tax_before  = progressive brackets(taxable_income)           # last bracket open-ended
credit_points_val  = credit_points * credit_point_value
pension_credit     = rate * max_contribution_rate * min(cash_income, income_ceiling)
income_tax         = max(0, income_tax_before - credit_points_val - pension_credit)
national_insurance = low_rate * min(taxable, threshold) + high_rate * (min(taxable, ceiling) - threshold)⁺
health             = same shape with the health rates
employee_pension   = cash_income * pension_pct
employee_study     = cash_income * study_fund_pct
net = cash_income + maintenance + electric_gross
      - income_tax - national_insurance - health
      - employee_pension - employee_study
      - participation - family_employee_share
```

- **Value of use** is taxable and in the NI/health base, but never cash and never pensionable.
- **Maintenance** (waiver, or an existing maintenance payment) is cash and taxable, not
  pensionable. For `Waiver()` it is the occupation's `waiver_maintenance`; a representative's
  quote overrides it (`Waiver(maintenance=X, maintenance_source="representative")`).
  `CurrentMaintenance` is for today only. The source is recorded in the metadata.
- **Electric gross-up** (only `drive == electric`, not plug-in or hybrid): the gross `G` with
  `net(G) − net(0) = net_bonus`, found by bisection on the full net function (60 fixed
  iterations), so `G` may cross a bracket or the NI threshold. `G` is **not rounded**
  (439.9085, 473.2160); the employee nets exactly 250. Method `gross` adds `gross_amount`.
- **Family track**: `employee_share = gap_split_employee × max(0, car cost − group budget)`,
  deducted from net (taxable income is unchanged). The car cost is the catalog's
  `monthly_company_cost`.
- **Participation** for a new car is the catalog default unless supplied; every result records
  its source (`employee_input`, `catalog_default`, `representative`).
- Every result's metadata carries both tax years (tables 2025, value of use 2026) and the
  rules version.

### Exactness and rounding

Nothing is rounded inside the calculation (`net_method.rounding.during: none`). The engine
runs in a Decimal context that traps `Inexact`, so any step that would have to round raises
instead. This is why `sum(delta_lines) == diff` holds exactly.

> Values from the engine carry more digits than Python's default 28-digit Decimal context.
> Send results out through `compass.engine.serialize.to_api_dict()` (exact values as
> fixed-point strings, display values as ints); never do Decimal arithmetic on them outside
> the engine. A seeded fuzz test (2,000 random profiles) checks that the engine never raises
> anything but `MissingInputs`.

Display rounding (`display: shekel`) is whole ILS, half-up, applied only at the boundary:

- `display_diff = round(alternative.net) − round(today.net)`, so the numbers on screen
  subtract correctly. This is how the reference sheet computes `net_diff` (E-003: exact
  −1,938.681, which rounds to −1,939; shown 13,109 − 15,047 = −1,938).
- `display_delta_lines` are the delta lines rounded by the largest-remainder method so they
  sum exactly to `display_diff` (the waterfall chart). Whole and zero lines never move.
- Delta lines use one convention, `net_effect`: positive = more money for the employee.

### Comparison, partial diff, eligibility

- `compare()` returns the exact `diff`, `delta_lines` (signed effect of each line on net) and
  `explanation_facts` (structured, e.g. `{"kind": "family_share", "amount": 1150}`; no prose).
- If only the contribution rates are unknown, the diff is still returned when it is the same at
  rates 0 and 0.2 (to the agora). The nets are then `None`, `missing` lists the rates and
  `display_diff = round(diff)`.
- `check_eligibility()` is separate from the calculation: ineligible scenarios are still
  calculated (shown as hypothetical). Reason codes: `car_group_within`, `car_group_higher`,
  `family_track`, `family_track_min_children`, `waiver_allowed`, `car_mandatory`,
  `waiver_not_allowed`, `current_arrangement`, and `needs_info` with `unknown_group`,
  `unknown_children`, `unknown_occupation`. The group is never inferred.
- Non-blocking `warnings` on comparisons and eligibility verdicts:
  `group_mismatch_with_occupation` (profile group ≠ occupation group) and
  `current_car_above_group` (today's car is from a higher group than the profile's).
- `list_options()` lists every catalog car and the waiver (if allowed), except today's
  arrangement: eligible first by diff, then needs_info, then not_eligible.

## Search

`compass/search/` matches what employees type to occupations and cars.

- `normalize()` runs on queries and candidates alike: case, whitespace and punctuation;
  geresh and apostrophes are dropped inside a word (`ג'י` = `גי`); Hebrew final letters;
  niqqud; gender forms (`מפתח/ת` → `מפתח`); letters split from digits (`atto3` = `atto 3`).
- Score = the mean of rapidfuzz `WRatio` and plain `ratio`. `WRatio` alone rewards matching
  only part of the query: the typo `קורולה קורס` scores 90.9 for COROLLA CROSS but also 90.0
  for COROLLA. The blend separates them (90.9 vs 80.3).
- `confident` = top score ≥ 85, a lead of ≥ 10 over the next candidate, **and** the top
  car's name is not strictly extended by another car's name. That last rule is why
  `קורולה` alone is **not** confident: it is an exact alias of COROLLA, but COROLLA CROSS's
  name extends it, and a wrong pick would silently change the value of use. We ask instead.
  Callers never auto-pick an unconfident result.
- Vehicles: catalog cars first (with `data/aliases.yaml`). Only when no catalog car scores
  70 does the search fall back to the Tax Authority dataset, returning up to 5 **full-key**
  records (`in_catalog: false`). A commercial name is not a key, so those usually tie and
  stay unconfident.

## Tools

`compass/tools/` is what the agent (Day 3) will call. Each tool is a Pydantic input model,
a handler and a description; `tool_definitions()` exports them in Anthropic format.
`ToolRunner.run(session_id, name, input)` validates, executes and persists, and **never
raises**: it returns `{"ok": true, ...}` or `{"ok": false, "error": {"code": ...}}` with
`invalid_input`, `missing_inputs` (`fields`, and which are `unknown` / `pending_rep`),
`not_found`, `ambiguous` (`candidates`), `not_eligible` (`reason`) or `internal_error`.
Tools return numbers **only** from the engine or the data files; none calculates money.

| Tool | What it does |
|---|---|
| `save_profile` | Stores any stated details (percentages in percent: 6.5 → 0.065). `occupation_query` is searched; if confident it also sets the group (source `derived`) unless the employee stated one. Returns `saved`, `missing`, `unknown`, `warnings` and `payslip_fields_unknown` (drives the "upload payslip" button). |
| `lookup_occupation` | Search result plus each occupation's group, car_mandatory, waiver_allowed and waiver_maintenance. |
| `lookup_vehicle` | Search result plus each car's group, drive, value of use, default participation and `in_catalog`. |
| `set_current_situation` | Today: a company car (catalog id, or a Tax Authority key from `lookup_vehicle`, which needs the participation), a maintenance payment, or none. Returns warnings such as `current_car_above_group` / `current_car_not_in_catalog`. |
| `check_eligibility` | Engine verdict for an alternative; `not_eligible` with the reason, or `missing_inputs`. |
| `compare` | Engine comparison of today vs an alternative (`to_api_dict`), stored as the session's last comparison (`comparison_ready`). Ineligible alternatives are still calculated and marked `hypothetical`; unknown contribution rates give a partial result. Also returns the alternative's `participation_source` and `pending_rep` (see below). |
| `list_options` | Every catalog car and the waiver (if allowed) with eligibility and diff vs today. Each car's participation is resolved exactly as in `compare` (optional `participation: {car_id: amount}` for amounts the employee stated), so an option and a single comparison of it always show the same numbers. |
| `get_rule` | A whitelisted rule (`budgets`, `choose_from`, `unused_budget`, `electric_bonus`, `family_track`, `waiver`, `participation`, `value_of_use`, `tax_tables_year`): value + the official Hebrew note. |
| `ask_representative` | Opens a ticket with a context snapshot; its blocking fields (profile fields, `current_participation` or `alternative_participation:<car_id>`) become `pending_rep` and the session `waiting_for_rep`. |

Profile slots hold a value, a state (`filled`, `unknown`, `pending_rep`) and a source
(`employee`, `payslip`, `representative`, `derived`). Only filled slots reach the engine;
nothing unknown is ever replaced by a "typical" value. There is no national-ID field, and a
`display_name` that looks like an ID number is rejected.

### Participation from a representative

The challenge's core scenario: the new car's participation is unknown, so the agent asks a
representative, who answers (say 350 ₪), and the conversation continues with that amount.

- Two fields only a representative fills (as ticket blocking fields):
  `current_participation` (today's car) and `alternative_participation:<car_id>`. The slot
  value is `{amount, effective_from}`; the answer may carry an `effective_from` date.
- `compare` resolves the participation per car: an amount stated in the call wins
  (`employee_input`); else a representative's answer (`representative`); else the catalog
  default (`catalog_default`). While a ticket blocking that car's participation is open, it
  computes with the default but returns `pending_rep: true`, so the agent never presents it
  as final. Today's car gets the same treatment (`today_participation`).
- `list_options` applies the same resolution to every car and returns the same
  `participation_source` / `pending_rep` per option; a test checks every option against a
  single `compare` of it, before, during and after a ticket.

## API

```sh
uv run python tasks.py serve                       # http://127.0.0.1:8000/docs
COMPASS_DEV_TOOLS=1 uv run python tasks.py serve   # also enable the dev tools endpoint
```

Settings come from the environment: `COMPASS_APP_DB` (default `data/app.db`),
`COMPASS_RULES` (default `data/rules.yaml`), `COMPASS_DEV_TOOLS=1`, `COMPASS_REP_TOKEN`,
`COMPASS_ADMIN_TOKEN`, `COMPASS_CORS_ORIGINS` (default: the Vite dev server). The session
store is created on startup.

| Method & path | Purpose |
|---|---|
| `POST /api/sessions` | Create a session → `{id}` |
| `GET /api/sessions/{id}` | Full snapshot for a refresh: messages, slots, scenarios, open tickets, last comparison, last event seq |
| `POST /api/sessions/{id}/messages` | Store a user message (202) and hand it to the `AgentRunner` (a no-op until Day 3) |
| `GET /api/sessions/{id}/events` | Server-sent events: replays everything after `Last-Event-ID` (or `?after=`), then streams live; heartbeat every 15 s |
| `POST /api/sessions/{id}/tools/{name}` | Run a tool directly: **dev / demo only** (`COMPASS_DEV_TOOLS=1`, otherwise 404) |
| `GET /api/tickets?status=open` | Representative inbox (**rep token**) |
| `POST /api/tickets/{id}/answer` | `{answer_text?, quick_answer_id?, values?, effective_from?}` (**rep token**): values are validated like `save_profile` and fill the blocking fields (source `representative`); blocking fields left without a value become `unknown`. Resumes the session and appends `ticket_answered` to the employee's stream |
| `GET /api/rules`, `/api/catalog`, `/api/occupations` | Read-only data for the UI (money as exact strings) |
| `POST /api/admin/reload-rules` | Re-read and validate `rules.yaml` live (**admin token**). Invalid → 422 with the readable message, and the previous rules stay active |
| `GET /api/health` | ok, the rules version and SHA-256, and the data versions |

The events table is the single source for the live UI: every state change appends an event
(`session_created`, `session_status`, `user_message`, `assistant_message`,
`profile_updated`, `current_situation_set`, `comparison_ready`, `ticket_opened`,
`ticket_answered`), and the SSE stream replays them by `seq`.

**Access.** `/api/tickets*` needs `Authorization: Bearer $COMPASS_REP_TOKEN` and
`/api/admin/*` needs `Authorization: Bearer $COMPASS_ADMIN_TOKEN` (shared tokens, compared in
constant time). If a token's variable is unset, its endpoints answer **503 "not
configured"**, never open by default; a missing or wrong token is 401. The dev tools
endpoint stays behind `COMPASS_DEV_TOOLS=1` and no token opens it.

## Rules: our additions to the official file

[data/rules.yaml](data/rules.yaml) keeps every value from the official rules file. The
updated edition of that file (see [raw/README.md](raw/README.md) for its SHA-256) officially
confirmed most of the rules we had previously reverse-engineered: the family-track cars and
per-car catalogue price, the pension-credit `maxContributionRate` (0.07), the contributions
base (`gross` = base + commissions + bonus), the participation treatment (net deduction, does
not reduce value of use) and the rounding policy (none during the calculation, whole shekel
for display only, which also overrides our earlier `electric.rounding: ceil`).

Only these values are still **our own additions**, marked `# added:` in the YAML:

| Rule | Value | Basis |
|---|---|---|
| `electric.method: gross` + `gross_amount: 250` | option | The Excel mentions a "250 ₪ gross" alternative that the official file does not contain. The default stays `gross_up`. |
| `value_of_use.tax_year` | `2026` | The dataset's tax year. It has to be explicit because it differs from the net-method tables' year (`net_method.tax_year: 2025`); both appear in every engine result. |

The loader rejects invalid edits and names the bad field, for example:

```
Invalid rules file data/rules.yaml:
  - electric.method: Input should be 'gross_up' or 'gross' (got 'grossup')
  - net_method.brackets[2].rate: must be between 0 and 1 (got 1.4)
  - net_method.national_insurance: threshold (70000) must be lower than ceiling (50695)
```
