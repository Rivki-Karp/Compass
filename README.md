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

Planned layers, not built yet: `compass/engine/` (deterministic net calculation),
`compass/agent/` (Claude tool-use loop), `api/` (FastAPI + SSE), `web/` (React).

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

## Rules: derived values pending organizer confirmation

[data/rules.yaml](data/rules.yaml) keeps every value from the source rules file. The rules
below are **not** in that file. Each one is marked `# derived:` in the YAML.

| Rule | Value | Basis |
|---|---|---|
| `net_method.contribution_base` | `[base_salary, commissions, bonus]` | Verified against all 12 reference results. Pension and study fund are not calculated on value of use, the electric gross-up or waiver maintenance. |
| `net_method.pension_credit.max_contribution_rate` | `0.07` | Verified against the reference results. Credit = 0.35 × 0.07 × min(income, 9,500), whatever the employee's actual pension %. |
| `electric.rounding` | `ceil` | Verified against the reference results. The gross-up is rounded up to a whole ILS (440 / 473). |
| `electric.method: gross` + `gross_amount: 250` | option | The Excel mentions a "250 ₪ gross" alternative that the source rules file does not contain. The default stays `gross_up`. |
| Family-track car cost **per car** | `catalog.monthly_company_cost` | Per the Excel and PDF: CARNIVAL 6,000, SANTA FE 5,600. It replaces the single `familyTrack.carPrice: 6000` in the source. |

The loader rejects invalid edits and names the bad field, for example:

```
Invalid rules file data/rules.yaml:
  - electric.method: Input should be 'gross_up' or 'gross' (got 'grossup')
  - net_method.brackets[2].rate: must be between 0 and 1 (got 1.4)
  - net_method.national_insurance: threshold (70000) must be lower than ceiling (50695)
```
