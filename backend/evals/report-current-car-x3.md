# Compass agent evals

- Run: 2026-10-19 17:33 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 3/3** · scenario runs passing: 9/9
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.2971 · total spend $7.8179 of the $30.00 cap (before this run: $7.5208)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| unknown_current_car | 3/3 | 2.0 | 3.0 | 13.4 | 2,109 / 1,231 / 77,081 | 0.0330 | 0 / 0 |
| rep_identifies_car | 3/3 | 2.0 | 3.7 | 20.5 | 6,220 / 1,665 / 96,897 | 0.0516 | 0 / 0 |
| options_without_current_car | 3/3 | 1.0 | 1.0 | 9.1 | 6 / 796 / 32,331 | 0.0144 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### unknown_current_car (repeat 1): PASS

- ✅ tool_called {'name': 'search_catalog', 'ok': True, 'turn': 0} — t0 search_catalog {'query': 'יונדאי'}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'car_id': 'CAR-08'}}} — t1 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-08', 'registration_year': 2026, 'participation': 300}}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'has_diff': True, 'today_unknown': False} — t1 has_diff=True, today_unknown=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### unknown_current_car (repeat 2): PASS

- ✅ tool_called {'name': 'search_catalog', 'ok': True, 'turn': 0} — t0 search_catalog {'query': 'יונדאי'}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'car_id': 'CAR-08'}}} — t1 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-08', 'registration_year': 2026, 'participation': 300}}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'has_diff': True, 'today_unknown': False} — t1 has_diff=True, today_unknown=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### unknown_current_car (repeat 3): PASS

- ✅ tool_called {'name': 'search_catalog', 'ok': True, 'turn': 0} — t0 search_catalog {'query': 'יונדאי'}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'car_id': 'CAR-08'}}} — t1 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-08', 'registration_year': 2026, 'participation': 300}}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'has_diff': True, 'today_unknown': False} — t1 has_diff=True, today_unknown=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### rep_identifies_car (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה. על הרכב כתוב משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. מבקשת לזהות את הרכב מהקטלוג. היא שוקלת מעבר ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': "איזה רכב צמוד יש לעובדת? על הרכב כתוב משהו כמו 'מציון'."}]}
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'העובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת מה דגם הרכב הצמוד שלה. כתוב עליו משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. נא לזהות את הרכב מהקטלוג.', 'questions': [{'bound_field': 'current_car', 'car_query': 'כתוב עליו משהו כמו מציון', 'prompt_he': 'איזה רכב צמוד רשום לעובדת?'}]}
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה. כתוב עליו משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. חיפוש בקטלוג לא העלה תוצאה. נבקש לזהות את הרכב. היא שוקלת מעבר ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': "איזה רכב צמוד רשום לעובדת? כתוב עליו משהו כמו 'מציון'."}]}
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

### options_without_current_car (repeat 1): PASS

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### options_without_current_car (repeat 2): PASS

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### options_without_current_car (repeat 3): PASS

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
