# raw/ — challenge input files

The files in this directory are **not committed** (see `.gitignore`). To rebuild
the generated data, put them here under the names below and run
`uv run python tasks.py data`.

They were renamed from the names they were distributed under (on 2026-10-14) so
the scripts can use short ASCII paths. The SHA-256 lets you check you have the
same version.

| File | Original filename (as distributed) | Content | SHA-256 |
|---|---|---|---|
| `strauss-rules.json` | `קובץ הכללים לדוגמה - תקציבים, מסלולים, שיטת הנטו (JSON).json` | Challenge rules: budgets, groups, electric bonus, family track, waiver, net method (2025 tax tables), value-of-use key and drive mapping. Version `mock-2026-10-12`. | `38b666024728fc4f820909144aca189f37f60954dfd882ce2b2faa0a1427f99e` |
| `value_of_use_2026.csv` | `מאגר שווי שימוש ברכב 2026 - הקובץ המורחב של רשות המסים (CSV, 77,988 רשומות).csv` | Israel Tax Authority, extended "value of use" (שווי שימוש) dataset, tax year 2026. 77,988 rows, 19 columns, encoding windows-1255, fields padded with spaces. | `fa101574386b582d98b06ddd671590ab894d680c152b5fe828e5172e186f939b` |
| `strauss_challenge_data.xlsx` | `נתוני האתגר - כללים, קטלוג רכבים, עיסוקים, 6 עובדים לדוגמה וחישובים (Excel).xlsx` | Sheets `קרא אותי`, `כללים ונתונים`, `קטלוג רכבים` (20 cars), `עיסוקים` (14 occupations), `עובדים לדוגמה` (6 employees), `חישובים` (reference results). Fictitious, except the manufacturer/model codes and value of use, which come from the Tax Authority dataset. | `9218b15a7fc5b47fe14db9533efea4123b6648948edded2b20aefb2d07422285` |
| `challenge_brief.pdf` | `הנחיות האתגר - שטראוס (PDF).pdf` | Challenge brief (4 pages, Hebrew): scenario, business rules, components, data sources. Reference only; no script reads it. | `154cbb11bcfae202d4cffa3890e4bcfdba95278c32e45b5c3eff6b3a1a1ecfb5` |

Source: the challenge page of the "קוד פתוח" AI Hackathon 2026, published in partnership
with Strauss Group.

## Known issues in `value_of_use_2026.csv`

Everything below is **documented and left as-is**. The ETL does not "fix" any source
values; it only strips padding and converts types.

### `drive_code`: the header disagrees with the data

Column 11's header reads `1-חשמלי.2-היברידי.3-פלג-אין` (1 = electric, 2 = hybrid,
3 = plug-in). The data doesn't follow it. It follows the mapping in the rules file
(`valueOfUse.driveField`):

| code | meaning |
|---|---|
| 0 | petrol / non-electrified (בנזין) |
| 1 | hybrid (היברידי) |
| 2 | plug-in hybrid (פלאג-אין) |
| 3 | electric (חשמלי) |

Checked against known models (tax year 2026, registration year 2025, private):
BYD ATTO 3 / DOLPHIN = 3, Toyota YARIS CROSS HSD = 1, Kia PICANTO = 0. Fuel type also
agrees: every row with fuel type 4 except one has `drive_code` 3. We store the raw code
in `vehicles.drive_code` and use the rules-file mapping.
`tests/test_vehicles_db.py::test_drive_code_follows_rules_mapping_not_csv_header`
locks this in.

### Model codes are reused across vehicle types

`(manufacturer_code, model_code, registration_year)` does **not** identify one vehicle.
For example, `01014` / `00003` / 2025 gives two different cars:

| vehicle_type_code | commercial_name | value_of_use |
|---|---|---|
| 1 (private) | ATTO 3 | 3,130 |
| 2 (commercial) | TANG | 6,950 |

Only the full official key (tax year + registration year + vehicle type + manufacturer
code + model code) identifies a row.

### Commercial name is not a key

One commercial name can map to many model codes with different values. For example,
"YARIS CROSS HSD", registration year 2025, private, has at least 5 model codes, with
value_of_use from 3,330 to 3,480. A name-based lookup must return candidates and never
pick one automatically.

### `fuel_type_code` combinations not explained by any source

`fuel_type_code` is stored as a raw integer with **no labels**, because no source file
defines them. Counts of fuel type × drive_code:

| fuel_type_code | drive_code | rows | note |
|---|---|---|---|
| 1 | 0 | 42,301 | |
| 2 | 0 | 12,346 | |
| 4 | 3 | 7,900 | |
| 7 | 2 | 7,754 | |
| 1 | 1 | 6,963 | |
| 8 | 2 | 361 | |
| 2 | 1 | 360 | fuel type 2 combined with hybrid |
| 6 | 0 | 2 | fuel type 6 appears only twice |
| 4 | 2 | 1 | fuel type 4 (otherwise always electric) marked plug-in |
