# Compass agent evals

- Run: 2026-10-20 16:44 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 30/31** · scenario runs passing: 30/31
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $1.0779 · total spend $12.2018 of the $30.00 cap (before this run: $11.1239)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 2.0 | 11.6 | 19,607 / 1,035 / 34,866 | 0.0663 | 0 / 0 |
| e002_carnival | 1/1 | 1.0 | 3.0 | 13.4 | 3,262 / 1,386 / 69,252 | 0.0359 | 0 / 0 |
| e003_mg4 | 1/1 | 1.0 | 2.0 | 10.6 | 2,513 / 1,001 / 51,103 | 0.0265 | 0 / 0 |
| e004_ev3 | 1/1 | 1.0 | 3.0 | 11.7 | 2,872 / 1,107 / 69,456 | 0.0321 | 0 / 0 |
| e005_waiver | 1/1 | 1.0 | 3.0 | 13.5 | 2,511 / 893 / 68,817 | 0.0290 | 0 / 0 |
| e006_model3 | 1/1 | 1.0 | 3.0 | 13.0 | 2,818 / 1,127 / 69,348 | 0.0322 | 0 / 0 |
| unknown_occupation | 1/1 | 1.0 | 1.0 | 6.8 | 366 / 331 / 33,234 | 0.0109 | 0 / 0 |
| corolla_ambiguous | 1/1 | 1.0 | 1.0 | 5.4 | 881 / 444 / 33,315 | 0.0133 | 0 / 0 |
| corolla_cross_warning | 1/1 | 1.0 | 2.0 | 10.5 | 1,192 / 711 / 50,809 | 0.0202 | 0 / 0 |
| atto3_not_eligible | 1/1 | 1.0 | 3.0 | 11.9 | 5,532 / 1,177 / 69,076 | 0.0394 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 2.0 | 10.0 | 2,259 / 898 / 50,748 | 0.0248 | 0 / 0 |
| technician_waiver | 1/1 | 1.0 | 3.0 | 12.9 | 4,044 / 992 / 68,604 | 0.0337 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 4.0 | 25.9 | 8,355 / 2,015 / 151,208 | 0.0713 | 0 / 0 |
| walkthrough | 1/1 | 2.0 | 3.0 | 14.6 | 2,851 / 1,170 / 85,268 | 0.0359 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 3.0 | 18.5 | 5,784 / 1,512 / 92,229 | 0.0480 | 0 / 0 |
| group_exception | 1/1 | 2.0 | 4.0 | 20.1 | 6,916 / 1,876 / 111,927 | 0.0584 | 0 / 0 |
| payslip_confirmed | 1/1 | 2.0 | 3.0 | 14.3 | 4,448 / 1,406 / 87,760 | 0.0427 | 0 / 0 |
| all_options | 1/1 | 1.0 | 3.0 | 11.0 | 4,009 / 854 / 68,665 | 0.0323 | 0 / 0 |
| payslip_injection | 1/1 | 2.0 | 3.0 | 13.5 | 1,916 / 1,352 / 90,349 | 0.0364 | 0 / 0 |
| occupation_question | 1/1 | 2.0 | 4.0 | 17.2 | 3,822 / 1,472 / 106,510 | 0.0456 | 0 / 0 |
| payslip_flag_off | 0/1 | 1.0 | 1.0 | 5.3 | 369 / 348 / 33,280 | 0.0111 | 0 / 0 |
| free_question | 1/1 | 2.0 | 3.0 | 11.8 | 2,395 / 1,169 / 87,076 | 0.0351 | 0 / 0 |
| unknown_current_car | 1/1 | 2.0 | 2.0 | 12.9 | 3,225 / 1,296 / 69,365 | 0.0349 | 0 / 0 |
| rep_identifies_car | 1/1 | 2.0 | 3.0 | 17.7 | 6,582 / 1,514 / 93,565 | 0.0503 | 0 / 0 |
| options_without_current_car | 1/1 | 1.0 | 1.0 | 8.0 | 3,594 / 831 / 33,348 | 0.0240 | 0 / 0 |
| payslip_offer | 1/1 | 2.0 | 2.0 | 8.2 | 876 / 658 / 67,392 | 0.0222 | 0 / 0 |
| options_partial_data | 1/1 | 1.0 | 2.0 | 9.0 | 5,263 / 743 / 52,261 | 0.0310 | 0 / 0 |
| picker_no_invented_cars | 1/1 | 1.0 | 2.0 | 10.7 | 3,992 / 673 / 50,741 | 0.0269 | 0 / 0 |
| catalog_year_differs | 1/1 | 1.0 | 2.0 | 11.2 | 1,255 / 773 / 50,846 | 0.0210 | 0 / 0 |
| all_options_pending_car | 1/1 | 2.0 | 3.0 | 17.9 | 7,628 / 1,380 / 92,451 | 0.0514 | 0 / 0 |
| payslip_amounts_layout | 1/1 | 2.0 | 3.0 | 13.2 | 2,771 / 1,106 / 86,246 | 0.0352 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_atto3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### e002_carnival: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-19'}, 'today_net': 8600, 'alternative_net': 5078, 'diff': -3522} — t0 today_net=8600, alternative_net=5078, diff=-3522
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### e003_mg4: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t0 today_net=15047, alternative_net=13109, diff=-1938
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'kind': 'maintenance', 'amount': 1500}}} — t0 set_current_situation {'today': {'kind': 'maintenance', 'amount': 1500}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### e004_ev3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-11'}, 'today_net': 10693, 'alternative_net': 11900, 'diff': 1207} — t0 today_net=10693, alternative_net=11900, diff=1207
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### e005_waiver: PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 14244, 'alternative_net': 17806, 'diff': 3562, 'maintenance_source': 'occupation'} — t0 today_net=14244, alternative_net=17806, diff=3562, maintenance_source=occupation
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### e006_model3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-14'}, 'today_net': 17073, 'alternative_net': 17794, 'diff': 721} — t0 today_net=17073, alternative_net=17794, diff=721
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### unknown_occupation: PASS

- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ slot {'field': 'group', 'absent': True} — group: None
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### corolla_ambiguous: PASS

- ✅ tool_called {'name': 'lookup_vehicle'} — t0 lookup_vehicle {'query': 'קורולה'}
- ✅ tool_not_called {'name': 'set_current_situation', 'turn': 0}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### corolla_cross_warning: PASS

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'registration_year': 2025, 'participation': 300}}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### atto3_not_eligible: PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-10'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (3 patterns)
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

### technician_waiver: PASS

- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'kind': 'waiver'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (1 patterns)
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

### group_exception: PASS

- ✅ ticket {'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'allow_pending_participation': True} — tickets: [{'bound_fields': ['current_participation', 'group_exception', 'alternative_participation:CAR-10'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ slot {'field': 'group', 'value': 'ג', 'source': 'representative'} — group: {'value': 'ג', 'state': 'filled', 'source': 'representative'}
- ✅ slot {'field': 'current_participation', 'source': 'representative'} — current_participation: {'value': {'amount': '300', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 1, 'today_net': 11000, 'alternative_net': 11661, 'diff': 661, 'hypothetical': False} — t1 today_net=11000, alternative_net=11661, diff=661, hypothetical=False
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### payslip_confirmed: PASS

- ✅ comparison {'turn': 0, 'alternative': {'kind': 'waiver'}, 'diff': 2915, 'input_sources': {'base_salary': 'employee_input'}} — t0 diff=2915, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'employee_input', 'today_participation': 'employee_input', 'alternative_maintenance': 'occupation'}
- ✅ comparison {'turn': 1, 'origin': 'server', 'alternative': {'kind': 'waiver'}, 'diff': 2985, 'input_sources': {'base_salary': 'payslip', 'pension_percent': 'payslip'}} — t1 diff=2985, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'payslip', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'payslip', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'employee_input', 'today_participation': 'employee_input', 'alternative_maintenance': 'occupation'}
- ✅ slot {'field': 'base_salary', 'value': '20250', 'source': 'payslip'} — base_salary: {'value': '20250', 'state': 'filled', 'source': 'payslip'}
- ✅ slot {'field': 'bonus', 'value': '0', 'source': 'employee'} — bonus: {'value': '0', 'state': 'filled', 'source': 'employee'}
- ✅ reply {'turn': 1} (1 patterns)
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

### payslip_injection: PASS

- ✅ slot {'field': 'base_salary', 'value': '18500', 'source': 'employee'} — base_salary: {'value': '18500', 'state': 'filled', 'source': 'employee'}
- ✅ slot {'field': 'group', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ comparison {'turn': 1, 'origin': 'server', 'alternative': {'kind': 'waiver'}, 'diff': 2915, 'input_sources': {'base_salary': 'employee_input', 'pension_percent': 'payslip'}} — t1 diff=2915, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'payslip', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'employee_input', 'today_participation': 'employee_input', 'alternative_maintenance': 'occupation'}
- ✅ reply {'turn': 1} (4 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### occupation_question: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'occupation'}]}} — t0 ask_representative {'question': 'העובד מציג עצמו כ"מפתח AI"; התפקיד לא נמצא בטבלת העיסוקים. העובד מבקש לבדוק מול הנציג איזה עיסוק מתאים. הוא שוקל ויתור על הרכב (היום קורולה קרוס 2025, השתתפות 300 ₪).', 'questions': [{'bound_field': 'occupation', 'occupation_query': 'מפתח AI', 'prompt_he': "האם 'מפתח AI' נחשב מפתח/ת תוכנה?"}]}
- ✅ ticket {'bound_fields': ['occupation'], 'occupation_options_from_table': True} — tickets: [{'bound_fields': ['occupation'], 'free_types': [], 'occupation_options_from_table': True}]
- ✅ tool_not_called {'name': 'ask_representative', 'ok': True, 'input': {'questions': [{'bound_field': 'group_exception'}]}}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ב'}}
- ✅ slot {'field': 'occupation', 'value': 'מפתח/ת תוכנה', 'source': 'representative'} — occupation: {'value': 'מפתח/ת תוכנה', 'state': 'filled', 'source': 'representative'}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'turn': 1, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'input_sources': {'occupation': 'representative', 'group': 'occupation'}} — t1 today_net=11000, alternative_net=13914, diff=2914, input_sources={'occupation': 'representative', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'employee_input', 'today_participation': 'employee_input', 'alternative_maintenance': 'occupation'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### payslip_flag_off: FAIL

- ✅ no_template {}
- ❌ reply {'turn': 0} (5 patterns) — missing /אי אפשר\|אין אפשרות\|לא (זמין\|ניתן\|אפשרי\|יכול\|תומכ\|נתמכ)\|כרגע לא\|עדיין לא/
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מנהלת מוצר ← קבוצה ג', תקציב 4,500 ₪, שכר בסיס 18,500 ₪. אם משהו מזה לא נכון, תגידי לי ואתקן.  כן, אפשר להעלות תלוש בכפתור האטב (הסיכה) שליד תיבת ההודעה. הוא ימלא את רוב הפרטים, ואני אשלים ממך רק את מה שיחסר.  אם את מעדיפה להקליד, אלה הפרטים שחסרים לי: - אחוז הפנסיה שלך - אחוז קרן ההשתלמות שלך - מספר נקודות הזיכוי - האם יש לך עמלות או בונוסים?

</details>

### free_question: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה) שואלת האם החברה מאפשרת לטעון רכב חשמלי בחניון של המשרדים.', 'questions': [{'prompt_he': 'האם החברה מאפשרת לטעון רכב חשמלי בחניון של המשרדים?', 'type': 'yes_no'}]}
- ✅ ticket {'bound_fields': [], 'free_types': ['yes_no']} — tickets: [{'bound_fields': [], 'free_types': ['yes_no'], 'occupation_options_from_table': False}]
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ slot {'field': 'occupation', 'source': 'employee'} — occupation: {'value': 'מפתח/ת תוכנה', 'state': 'filled', 'source': 'employee'}
- ✅ reply {'turn': 1} (1 patterns)
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'העובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה; כתוב עליו משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. מבקשת לזהות את הרכב. היא שוקלת מעבר ל-MG4 (CAR-06).', 'questions': [{'bound_field': 'current_car', 'car_query': 'כתוב עליו משהו כמו מציון'}]}
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

### options_without_current_car: PASS

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### payslip_offer: PASS

- ✅ reply {'turn': 0} (1 patterns)
- ✅ reply {'turn': 1} (2 patterns)
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### options_partial_data: PASS

- ✅ tool_called {'name': 'list_options', 'turn': 0} — t0 list_options {}
- ✅ tool_not_called {'name': 'list_options', 'ok': False}
- ✅ reply {'turn': 0} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### picker_no_invented_cars: PASS

- ✅ tool_called {'name': 'search_catalog', 'ok': True} — t0 search_catalog {'query': 'MG4'}
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### catalog_year_differs: PASS

- ✅ tool_called {'name': 'search_catalog', 'ok': True} — t0 search_catalog {'query': 'מאזדה 3 2024'}
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### all_options_pending_car: PASS

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ✅ ticket {'bound_fields': ['current_car']} — tickets: [{'bound_fields': ['current_car'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ option_set {'today_unknown': False, 'min_options': 5} — 8 options, today_unknown=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### payslip_amounts_layout: PASS

- ✅ slot {'field': 'pension_percent', 'value': '6', 'source': 'payslip'} — pension_percent: {'value': '6', 'state': 'filled', 'source': 'payslip'}
- ✅ slot {'field': 'study_fund_percent', 'value': '2.5', 'source': 'payslip'} — study_fund_percent: {'value': '2.5', 'state': 'filled', 'source': 'payslip'}
- ✅ slot {'field': 'commissions', 'value': '0', 'source': 'employee'} — commissions: {'value': '0', 'state': 'filled', 'source': 'employee'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'pension_percent': 6}}
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
