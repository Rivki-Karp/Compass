# Compass agent evals

- Run: 2026-10-20 14:23 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 2
- **Scenarios passing (every repeat): 1/2** · scenario runs passing: 3/4
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.1719 · total spend $9.6974 of the $30.00 cap (before this run: $9.5255)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| rep_identifies_car | 2/2 | 2.0 | 4.0 | 19.0 | 13,262 / 1,598 / 91,204 | 0.0674 | 0 / 0 |
| options_without_current_car | 1/2 | 1.0 | 1.0 | 8.6 | 1,791 / 799 / 30,545 | 0.0186 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### rep_identifies_car (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת את דגם הרכב הצמוד שלה. כתוב עליו משהו כמו "מציון". היא מצהירה שההשתתפות שלה 300 ₪ לחודש. נא לזהות את הרכב מהקטלוג. היא שוקלת מעבר ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': "איזה רכב צמוד יש לעובדת? כתוב עליו משהו כמו 'מציון'."}]}
- ✅ ticket {'bound_fields': ['current_car']} — tickets: [{'bound_fields': ['current_car'], 'free_types': [], 'occupation_options_from_table': False}]
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ slot {'field': 'current_car', 'value': 'CAR-07', 'source': 'representative'} — current_car: {'value': 'CAR-07', 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'turn': 1, 'has_diff': True, 'today_unknown': False, 'input_sources': {'today_car': 'representative'}} — t1 has_diff=True, today_unknown=False, input_sources={'occupation': 'employee_input', 'group': 'occupation', 'base_salary': 'employee_input', 'commissions': 'employee_input', 'bonus': 'employee_input', 'pension_percent': 'employee_input', 'study_fund_percent': 'employee_input', 'credit_points': 'employee_input', 'today_car': 'representative', 'today_participation': 'catalog_default', 'alternative_car': 'employee_input', 'alternative_participation': 'catalog_default'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### rep_identifies_car (repeat 2): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת (מפתחת תוכנה, קבוצה ב\') לא יודעת מה דגם רכב החברה הצמוד שלה. על הרכב כתוב משהו כמו "מציון". היא משתתפת ב-300 ₪ בחודש. מבקשת לזהות את הרכב מהקטלוג. היא שוקלת מעבר ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון', 'prompt_he': 'איזה רכב צמוד יש לעובדת? כתוב עליו משהו כמו "מציון".'}]}
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

### options_without_current_car (repeat 1): FAIL

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ❌ [global] no payslip unless the employee mentioned one — t0 payslip

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מנהלת מוצר ← קבוצה ג', תקציב 4,500 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6%, קרן השתלמות 2.5%, 2.75 נקודות זיכוי ו-2 ילדים מתחת לגיל 23.  הרכב של היום עוד לא ידוע, ולכן אין הפרש. אני מציג את הנטו המשוער של כל חלופה. ההפרש יופיע כשנדע מה הרכב שלך היום.  החלופות המובילות: - **ויתור על הרכב**: נטו משוער 14,231 ₪. החישוב מתייחס לשכר בלבד, ועלויות רכב פרטי אינן כלולות. - **MG4** (חשמלי, קבוצה ב'): 12,045 ₪. - **BYD DOLPHIN** (חשמלי, קבוצה א'): 12,026 ₪.  ההשתתפות בחלופות היא ברירת המחדל מהקטלוג. אפשר לראות ולבחור את כל החלופות הזכאיות בבורר שמעל כרטיס ההשוואה. הרכבים בקבוצה ד' והמסלול המשפחתי לא זמינים לך כרגע.  אפשר לבדוק מה הרכב הצמוד שלך היום, למשל בתלוש, ברישיון הרכב או בחוזה הרכב? אם לא תמצאי, אפשר לנסות לזהות אותו מרשימה או לשאול את נציג הרכב.

</details>

### options_without_current_car (repeat 2): PASS

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
