# Compass

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
uv run python tasks.py data      # rebuild all generated data from raw/ (needs the raw files)
uv run python tasks.py test      # run the tests
uv run python tasks.py lint      # ruff check + ruff format --check
uv run python tasks.py fmt       # apply formatting
uv run python tasks.py demo E-001  # Hebrew breakdown of a golden employee (E-001 … E-006)
```

If you have `make`, `make install|data|test|lint|fmt` does the same.

The raw challenge files are not committed. Put them in `raw/` under the names listed in
[raw/README.md](raw/README.md). `tasks.py data` is idempotent: it rebuilds `data/vehicles.db`
atomically and writes byte-identical JSON on every run.

## Project layout

```
compass/
  config.py            paths, resolved relative to the repo root
  rules.py             load_rules(): validated, frozen view of data/rules.yaml
  data/
    drive.py           drive_code -> petrol|hybrid|plugin|electric
    vehicles.py        get_value_of_use(), find_by_codes()          (vehicles.db)
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
  reference.py         the 6 golden fixtures as engine inputs (tests + demo)
  demo.py              `tasks.py demo E-00X`
data/
  rules.yaml           business rules: hand-edited, commented, validated on load
  catalog.json         20 company cars                  (generated from the Excel)
  occupations.json     14 occupations                   (generated from the Excel)
  vehicles.db          Tax Authority dataset in SQLite  (generated, git-ignored)
raw/                   raw challenge inputs (git-ignored, except raw/README.md)
scripts/
  build_vehicles_db.py raw CSV  -> data/vehicles.db
  extract_excel.py     raw xlsx -> data/*.json + tests/fixtures/reference_*.json
tests/                 pytest suite; fixtures/ holds the 6 golden reference employees
tasks.py               cross-platform task runner (Makefile wraps it)
```

Planned layers, not built yet: `compass/agent/` (Claude tool-use loop), `api/` (FastAPI +
SSE), `web/` (React). The engine imports none of them.

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
  pensionable. For `Waiver()` it is the occupation's `waiver_maintenance`.
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
> Do arithmetic on them inside `compass.engine.decimal_math.exact()`, or round them for
> display first.

Display rounding (`display: shekel`) is whole ILS, half-up, applied only at the boundary:

- `display_diff = round(alternative.net) − round(today.net)`, so the numbers on screen
  subtract correctly. This is how the reference sheet computes `net_diff` (E-003: exact
  −1,938.681, which rounds to −1,939; shown 13,109 − 15,047 = −1,938).
- `display_delta_lines` are the delta lines rounded by the largest-remainder method so they
  sum exactly to `display_diff` (the waterfall chart). Whole and zero lines never move.

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
- `list_options()` lists every catalog car and the waiver (if allowed), except today's
  arrangement: eligible first by diff, then needs_info, then not_eligible.

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
