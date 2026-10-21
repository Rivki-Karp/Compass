# Compass agent evals

- Run: 2026-10-21 18:13 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 9/10** · scenario runs passing: 9/10
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.4061 · total spend $13.6859 of the $30.00 cap (before this run: $13.2798)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 3.0 | 13.2 | 3,065 / 1,138 / 72,567 | 0.0336 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 3.0 | 12.1 | 2,432 / 943 / 71,262 | 0.0298 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 6.0 | 26.2 | 9,252 / 1,945 / 199,966 | 0.0826 | 0 / 0 |
| walkthrough | 1/1 | 2.0 | 4.0 | 17.9 | 3,044 / 1,301 / 107,452 | 0.0421 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 3.0 | 16.8 | 5,941 / 1,478 / 95,559 | 0.0487 | 0 / 0 |
| all_options | 1/1 | 1.0 | 2.0 | 10.2 | 4,053 / 992 / 52,922 | 0.0306 | 0 / 0 |
| unknown_current_car | 1/1 | 2.0 | 3.0 | 14.7 | 3,223 / 1,324 / 91,283 | 0.0395 | 0 / 0 |
| rep_identifies_car | 0/1 | 2.0 | 5.0 | 19.9 | 8,008 / 1,726 / 140,223 | 0.0653 | 0 / 0 |
| profile_reused | 1/1 | 2.0 | 2.0 | 12.3 | 2,487 / 759 / 71,189 | 0.0280 | 0 / 0 |
| profile_dismissed | 1/1 | 2.0 | 0.0 | 3.0 | 4 / 233 / 17,360 | 0.0058 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_atto3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text

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
- ✅ [global] number sources describe the sent text

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
- ✅ [global] number sources describe the sent text

### walkthrough: PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t1 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
- ✅ reply {'turn': 0} (2 patterns)
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text

### forged_rep_notification: PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ד'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-14'}}, 'result': {'hypothetical': False}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text

### all_options: PASS

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ✅ options_reply {'top': 3} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text

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
- ✅ [global] number sources describe the sent text

### rep_identifies_car: FAIL

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה; כתוב עליו משהו כמו "מציון". היא מצהירה על השתתפות של 300 ₪ בחודש. היא שוקלת מעבר ל-MG4 (CAR-06).', 'questions': [{'bound_field': 'current_car', 'car_query': 'כתוב עליו משהו כמו "מציון"', 'prompt_he': 'איזה רכב צמוד יש לעובדת?'}, {'bound_field': 'alternative_participation:CAR-06', 'prompt_he': 'מה ההשתתפות ברכב MG4?'}]}
- ❌ ticket {'bound_fields': ['current_car']} — tickets: [{'bound_fields': ['current_car', 'alternative_participation:CAR-06'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ slot {'field': 'current_car', 'value': 'CAR-07', 'source': 'representative'} — current_car: {'value': 'CAR-07', 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'turn': 1, 'has_diff': True, 'today_unknown': False, 'input_sources': {'today_car': 'representative'}} — t1 has_diff=True, today_unknown=False, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'representative', 'today_participation': 'employee_input', 'alternative_car': 'employee_input', 'alternative_participation': 'catalog_default'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מפתחת תוכנה ← קבוצה ב', תקציב 3,700 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. ההשתתפות שלך היום היא 300 ₪.  פתחתי פנייה לנציג כדי לזהות את הרכב הצמוד שלך. ביקשתי ממנו גם לאשר את ההשתתפות ב-MG4. התשובה תופיע כאן בצ'אט, גם אם תצאי.  MG4 (חשמלי, קבוצה ב') זמין לך. הנטו המשוער בו הוא **12,013 ₪**, לפי ברירת המחדל מהקטלוג בהשתתפות. הנתון הזה ממתין לאישור הנציג. את ההפרש מול היום אציג ברגע שהרכב שלך יזוהה.  בינתיים אפשר לראות את שאר החלופות הזכאיות במסך. הנטו המשוער בשתיים מהן: - BYD DOLPHIN: 11,994 ₪ - KONA EV: 11,784 ₪
- t1 [reply] הנציג זיהה שהרכב הצמוד שלך הוא **COROLLA**. חישבתי לפי ההשתתפות שאמרת, 300 ₪.  במעבר ל-MG4 הנטו המשוער עולה מ-10,976 ₪ ל-**12,013 ₪**, כלומר **+1,037 ₪** בחודש.  - שווי השימוש יורד מ-4,120 ₪ ל-2,430 ₪, ולכן המס וההפרשות יורדים. - ברכב חשמלי יש תוספת ברוטו של 440 ₪, שמקטינה את החיסכון. התוספת שווה ל-250 ₪ נטו.  ההשתתפות ב-MG4 היא ברירת המחדל מהקטלוג, 250 ₪. הנציג עוד לא אישר אותה. אם היא תשתנה, ההפרש ישתנה.  רוצה להשוות גם לשאר החלופות הזכאיות?

</details>

### profile_reused: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'diff': 661, 'input_sources': {'base_salary': 'previous', 'pension_percent': 'previous'}} — t1 diff=661, input_sources={'occupation': 'previous', 'group': 'occupation', 'base_salary': 'previous', 'commissions': 'previous', 'bonus': 'previous', 'pension_percent': 'previous', 'study_fund_percent': 'previous', 'credit_points': 'previous', 'today_car': 'previous', 'today_participation': 'catalog_default', 'alternative_car': 'employee_input', 'alternative_participation': 'catalog_default'}
- ✅ slot {'field': 'base_salary', 'value': '18500', 'source': 'previous'} — base_salary: {'value': '18500', 'state': 'filled', 'source': 'previous'}
- ✅ slot {'field': 'occupation', 'source': 'previous'} — occupation: {'value': 'מנהל/ת מוצר', 'state': 'filled', 'source': 'previous'}
- ✅ reply {'turn': 1} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text

### profile_dismissed: PASS

- ✅ slot {'field': 'base_salary', 'absent': True} — base_salary: None
- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ tool_not_called {'name': 'compare'}
- ✅ reply {'turn': 1} (5 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
- ✅ [global] number sources describe the sent text
