# Compass agent evals

- Run: 2026-10-19 15:42 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 19/19** · scenario runs passing: 19/19
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.6107 · total spend $6.6502 of the $30.00 cap (before this run: $6.0395)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 3.0 | 14.5 | 15,610 / 1,446 / 39,910 | 0.0615 | 0 / 0 |
| e002_carnival | 1/1 | 1.0 | 3.0 | 13.8 | 3,363 / 1,375 / 52,401 | 0.0326 | 0 / 0 |
| e003_mg4 | 1/1 | 1.0 | 2.0 | 9.5 | 2,433 / 934 / 37,966 | 0.0230 | 0 / 0 |
| e004_ev3 | 1/1 | 1.0 | 3.0 | 13.1 | 3,152 / 1,290 / 51,955 | 0.0312 | 0 / 0 |
| e005_waiver | 1/1 | 1.0 | 3.0 | 10.8 | 2,504 / 914 / 51,374 | 0.0257 | 0 / 0 |
| e006_model3 | 1/1 | 1.0 | 3.0 | 12.4 | 3,074 / 1,176 / 51,810 | 0.0298 | 0 / 0 |
| unknown_occupation | 1/1 | 1.0 | 1.0 | 4.9 | 366 / 282 / 24,516 | 0.0086 | 0 / 0 |
| corolla_ambiguous | 1/1 | 1.0 | 1.0 | 5.7 | 881 / 433 / 24,597 | 0.0114 | 0 / 0 |
| corolla_cross_warning | 1/1 | 1.0 | 2.0 | 8.5 | 1,185 / 764 / 37,732 | 0.0181 | 0 / 0 |
| atto3_not_eligible | 1/1 | 1.0 | 4.0 | 13.2 | 5,450 / 1,168 / 67,987 | 0.0389 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 3.0 | 12.4 | 2,425 / 907 / 51,127 | 0.0254 | 0 / 0 |
| technician_waiver | 1/1 | 1.0 | 3.0 | 11.4 | 4,022 / 979 / 51,161 | 0.0301 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 5.0 | 25.6 | 5,483 / 1,864 / 121,746 | 0.0567 | 0 / 0 |
| walkthrough | 1/1 | 2.0 | 4.0 | 14.3 | 3,060 / 1,317 / 77,316 | 0.0363 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 4.0 | 15.8 | 3,083 / 1,400 / 78,393 | 0.0374 | 0 / 0 |
| group_exception | 1/1 | 2.0 | 4.0 | 23.2 | 5,370 / 1,870 / 81,682 | 0.0485 | 0 / 0 |
| all_options | 1/1 | 1.0 | 3.0 | 9.3 | 3,990 / 874 / 51,222 | 0.0290 | 0 / 0 |
| occupation_question | 1/1 | 2.0 | 3.0 | 16.6 | 4,218 / 1,546 / 67,246 | 0.0394 | 0 / 0 |
| free_question | 1/1 | 2.0 | 2.0 | 12.0 | 2,335 / 1,097 / 52,282 | 0.0273 | 0 / 0 |

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

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'participation': 300, 'registration_year': 2025}}
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

- ✅ ticket {'bound_fields': ['current_participation', 'group_exception']} — tickets: [{'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'occupation_options_from_table': False}]
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

### all_options: PASS

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ✅ options_reply {'top': 3} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### occupation_question: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'occupation'}]}} — t0 ask_representative {'question': 'העובד מציג עצמו כמפתח AI; התפקיד לא נמצא בטבלת העיסוקים. הוא ביקש לבדוק מול הנציג. הוא שוקל ויתור על הרכב (קורולה קרוס 2025, השתתפות 300 ₪), וצריך לדעת את העיסוק כדי לגזור קבוצה ולבדוק זכאות לוויתור.', 'questions': [{'bound_field': 'occupation', 'occupation_query': 'מפתח AI', 'prompt_he': "האם 'מפתח AI' נחשב מפתח/ת תוכנה, או לאיזה עיסוק בטבלה הוא מתאים?"}]}
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

### free_question: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0} — t0 ask_representative {'question': 'העובדת שואלת האם החברה מאפשרת לטעון רכב חשמלי בחניון של המשרדים.', 'questions': [{'prompt_he': 'האם החברה מאפשרת לטעון רכב חשמלי בחניון של המשרדים?', 'type': 'yes_no'}]}
- ✅ ticket {'bound_fields': [], 'free_types': ['yes_no']} — tickets: [{'bound_fields': [], 'free_types': ['yes_no'], 'occupation_options_from_table': False}]
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ slot {'field': 'occupation', 'source': 'employee'} — occupation: {'value': 'מפתח/ת תוכנה', 'state': 'filled', 'source': 'employee'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
