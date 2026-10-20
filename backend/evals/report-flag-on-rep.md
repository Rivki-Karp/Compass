# Compass agent evals

- Run: 2026-10-20 14:25 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 1/1** · scenario runs passing: 3/3
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.1521 · total spend $9.8495 of the $30.00 cap (before this run: $9.6974)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| rep_identifies_car | 3/3 | 2.0 | 3.0 | 20.5 | 6,451 / 1,742 / 85,819 | 0.0507 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### rep_identifies_car (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה ומבקשת לברר. לדבריה כתוב עליו משהו כמו "מציון". היא מציינת השתתפות של 300 ₪. היא שוקלת מעבר ל-MG4 2025.', 'questions': [{'bound_field': 'current_car', 'car_query': 'משהו כמו מציון', 'prompt_he': "איזה רכב צמוד רשום לעובדת? היא זוכרת שכתוב עליו משהו כמו 'מציון'."}]}
- ✅ ticket {'bound_fields': ['current_car']} — tickets: [{'bound_fields': ['current_car'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ slot {'field': 'current_car', 'value': 'CAR-07', 'source': 'representative'} — current_car: {'value': 'CAR-07', 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'turn': 1, 'has_diff': True, 'today_unknown': False, 'input_sources': {'today_car': 'representative'}} — t1 has_diff=True, today_unknown=False, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'representative', 'today_participation': 'employee_input', 'alternative_car': 'employee_input', 'alternative_participation': 'catalog_default'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### rep_identifies_car (repeat 2): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') אינה יודעת את דגם הרכב הצמוד שלה. כתוב עליו משהו כמו "מציון", והחיפוש בקטלוג לא מצא התאמה. היא משתתפת ב-300 ₪ בחודש. היא מבקשת לבדוק איזה רכב רשום עליה, והיא שוקלת מעבר ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': 'איזה רכב צמוד רשום לעובדת? היא מתארת כיתוב כמו "מציון".'}]}
- ✅ ticket {'bound_fields': ['current_car']} — tickets: [{'bound_fields': ['current_car'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ slot {'field': 'current_car', 'value': 'CAR-07', 'source': 'representative'} — current_car: {'value': 'CAR-07', 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'turn': 1, 'has_diff': True, 'today_unknown': False, 'input_sources': {'today_car': 'representative'}} — t1 has_diff=True, today_unknown=False, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'representative', 'today_participation': 'employee_input', 'alternative_car': 'employee_input', 'alternative_participation': 'catalog_default'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### rep_identifies_car (repeat 3): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'העובדת מפתחת תוכנה (קבוצה ב\'), לא יודעת מה דגם הרכב הצמוד שלה. כתוב עליו משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. מבקשת לזהות את הרכב מהקטלוג. היא שוקלת מעבר ל-MG4 2025.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': "איזה רכב צמוד רשום לעובדת? היא זוכרת שכתוב עליו משהו כמו 'מציון'."}]}
- ✅ ticket {'bound_fields': ['current_car']} — tickets: [{'bound_fields': ['current_car'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ slot {'field': 'current_car', 'value': 'CAR-07', 'source': 'representative'} — current_car: {'value': 'CAR-07', 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'turn': 1, 'has_diff': True, 'today_unknown': False, 'input_sources': {'today_car': 'representative'}} — t1 has_diff=True, today_unknown=False, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'representative', 'today_participation': 'employee_input', 'alternative_car': 'employee_input', 'alternative_participation': 'catalog_default'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
