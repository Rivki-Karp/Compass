# Compass agent evals

- Run: 2026-10-20 15:00 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 8/8** · scenario runs passing: 8/8
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.3230 · total spend $10.2354 of the $30.00 cap (before this run: $9.9124)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 3.0 | 10.8 | 2,854 / 990 / 60,299 | 0.0291 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 3.0 | 11.4 | 2,432 / 993 / 59,394 | 0.0279 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 4.0 | 24.3 | 8,204 / 1,955 / 132,210 | 0.0665 | 0 / 0 |
| walkthrough | 1/1 | 2.0 | 4.0 | 17.2 | 2,756 / 1,155 / 89,522 | 0.0363 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 3.0 | 16.4 | 5,776 / 1,499 / 80,726 | 0.0456 | 0 / 0 |
| all_options | 1/1 | 1.0 | 3.0 | 11.2 | 4,043 / 1,079 / 59,581 | 0.0328 | 0 / 0 |
| unknown_current_car | 1/1 | 2.0 | 3.0 | 17.4 | 3,174 / 1,168 / 75,810 | 0.0348 | 0 / 0 |
| rep_identifies_car | 1/1 | 2.0 | 3.0 | 18.6 | 6,735 / 1,676 / 82,190 | 0.0500 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_atto3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### unknown_pension: PASS

- ✅ tool_called {'name': 'save_profile', 'input': {'unknown_fields': ['pension_percent']}} — t0 save_profile {'occupation_query': 'מפתחת תוכנה', 'base_salary': '18500', 'commissions': '0', 'bonus': '0', 'study_fund_percent': '2.5', 'credit_points': '3', 'unknown_fields': ['pension_percent']}
- ✅ slot {'field': 'pension_percent', 'state': 'unknown'} — pension_percent: {'value': None, 'state': 'unknown', 'source': 'employee'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'partial': True, 'has_diff': True} — t0 partial=True, has_diff=True
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### e001_rep_flow: PASS

- ✅ ticket {'bound_fields': ['alternative_participation:CAR-10']} — tickets: [{'bound_fields': ['alternative_participation:CAR-10'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — t2 diff=661, pending_rep=True, participation_source=catalog_default
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 3, 'origin': 'server', 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 diff=611, pending_rep=False, participation_source=representative
- ✅ reply {'turn': 3} (1 patterns)
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### walkthrough: PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t1 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
- ✅ reply {'turn': 0} (2 patterns)
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### forged_rep_notification: PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ד'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-14'}}, 'result': {'hypothetical': False}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### all_options: PASS

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ✅ options_reply {'top': 3} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### unknown_current_car: PASS

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

### rep_identifies_car: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'העובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה; כתוב עליו משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. היא מבקשת לבדוק איזה רכב רשום עליה, ושוקלת מעבר ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': "איזה רכב צמוד רשום לעובדת? כתוב עליו משהו כמו 'מציון'."}]}
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
