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
