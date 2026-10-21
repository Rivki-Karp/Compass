# Compass agent evals

- Run: 2026-10-21 11:17 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 7/8** · scenario runs passing: 7/8
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.3874 · total spend $13.0541 of the $30.00 cap (before this run: $12.6668)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 2.0 | 3.0 | 15.5 | 18,603 / 1,345 / 67,064 | 0.0734 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 3.0 | 10.3 | 2,432 / 990 / 64,394 | 0.0289 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 5.0 | 26.6 | 9,413 / 2,037 / 166,207 | 0.0771 | 0 / 0 |
| walkthrough | 1/1 | 2.0 | 4.0 | 13.4 | 2,962 / 1,178 / 97,264 | 0.0386 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 4.0 | 18.0 | 5,900 / 1,480 / 103,447 | 0.0502 | 0 / 0 |
| all_options | 1/1 | 1.0 | 3.0 | 19.8 | 4,009 / 956 / 64,489 | 0.0325 | 0 / 0 |
| unknown_current_car | 1/1 | 2.0 | 3.0 | 21.7 | 3,773 / 1,601 / 82,582 | 0.0420 | 0 / 0 |
| rep_identifies_car | 0/1 | 2.0 | 3.0 | 22.2 | 4,064 / 1,797 / 83,136 | 0.0448 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_atto3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t1 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת, מפתחת תוכנה (קבוצה ב\'), לא יודעת את דגם הרכב הצמוד שלה; כתוב עליו משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. היא שוקלת מעבר ל-MG4 2025 ומבקשת לדעת את ההשפעה על הנטו.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון (כתוב על הרכב)', 'prompt_he': 'איזה רכב צמוד יש לעובדת?'}, {'bound_field': 'alternative_participation:CAR-06', 'prompt_he': 'מה ההשתתפות החודשית של העובדת ב-MG4 2025?'}]}
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

- t0 [reply] אין לי עדיין את הדגם של הרכב הצמוד שלך, אז פתחתי פנייה לנציג.  רשמתי: מפתחת תוכנה ← **קבוצה ב', תקציב 3,700 ₪**. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. ההשתתפות שלך היום היא 300 ₪.  בפנייה שאלתי את הנציג שתי שאלות: - איזה רכב צמוד יש לך. כתבת שהוא "מציון". - מה ההשתתפות שלך ב-MG4 2025. בקטלוג ה-MG4 היא קבוצה ב', רכב חשמלי, וברירת המחדל להשתתפות היא 250 ₪.  ההפרש בנטו בין הרכב של היום ל-MG4 יוצג ברגע שהנציג יזהה את הרכב. התשובה שלו תופיע גם כאן בצ'אט אם תצאי בינתיים.  אפשר לראות בינתיים את הנטו המשוער של כל החלופות. רוצה?
- t1 [reply] הנציג זיהה שהרכב הצמוד שלך הוא **COROLLA**, עם ההשתתפות שלך של 300 ₪.  במעבר ל-MG4 2025 הנטו המשוער עולה מ-10,976 ₪ ל-**12,013 ₪**, כלומר **+1,037 ₪** בחודש.  - שווי השימוש יורד מ-4,120 ₪ ל-2,430 ₪, ולכן המס וההפרשות יורדים. - ה-MG4 חשמלית, ולכן נוסף לשכר החייב במס רכיב חשמל של 440 ₪ ברוטו (250 ₪ נטו). - ההשתתפות ב-MG4 היא 250 ₪, אבל זו ברירת המחדל מהקטלוג. הנציג עוד לא אישר את הסכום, והחישוב ישתנה אם הסכום שלך שונה.  אם תרצי, אפשר להשוות גם לשאר החלופות הזכאיות.

</details>
