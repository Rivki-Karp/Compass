# Compass agent evals

- Run: 2026-10-19 15:58 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 1/2** · scenario runs passing: 1/2
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.1133 · total spend $6.9573 of the $30.00 cap (before this run: $6.8439)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| group_exception | 0/1 | 2.0 | 3.0 | 18.8 | 17,590 / 1,802 / 55,139 | 0.0730 | 0 / 0 |
| occupation_question | 1/1 | 2.0 | 3.0 | 18.2 | 4,128 / 1,657 / 67,165 | 0.0403 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### group_exception: FAIL

- ❌ ticket {'bound_fields': ['current_participation', 'group_exception']} — tickets: [{'bound_fields': ['group_exception', 'current_participation', 'alternative_participation:CAR-10'], 'free_types': [], 'occupation_options_from_table': False}]
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

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מפתח תוכנה ← קבוצה ב', תקציב 3,700 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים (0), פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. הרכב הנוכחי הוא קורולה קרוס 2025.  פתחתי פנייה לנציג עם שלוש שאלות: אישור החריג לקבוצה ג', ההשתתפות הנוכחית שלך, וההשתתפות ב-ATTO 3. אפשר להמשיך בינתיים, והתשובה תופיע בצ'אט גם אם תצא.  ATTO 3 2025 היא קבוצה ג', והקבוצה שלך כרגע ב'. לכן המעבר אליה לא זכאי בלי אישור, והחישוב כאן **היפותטי** ובתנאי לאישור.  - **נטו משוער:** היום 11,000 ₪, עם ATTO 3 11,661 ₪. ההפרש הוא **+661 ₪**. - **למה:** שווי השימוש יורד מ-4,070 ₪ ל-3,130 ₪. ברכב חשמלי נוסף החזר חשמל של 440 ₪ ברוטו. - **השתתפות:** בשני הרכבים ההשתתפות היא ברירת המחדל מהקטלוג, 300 ₪, עד לאישור הנציג.  רוצה שאראה גם חלופות זכאיות בקבוצה ב'?
- t1 [reply] הנציג ענה על שתיים מהשלוש:  - **חריג הקבוצה:** אושר. הקבוצה עודכנה לג', תקציב 4,500 ₪. ATTO 3 זכאית עכשיו. - **ההשתתפות הנוכחית:** 300 ₪. - **ההשתתפות ב-ATTO 3:** עדיין ממתינה לנציג. בינתיים החישוב משתמש בברירת המחדל מהקטלוג, 300 ₪.  הנטו המשוער היום הוא 11,000 ₪, ועם ATTO 3 הוא 11,661 ₪. ההפרש הוא **+661 ₪**.  המנגנון: שווי השימוש יורד מ-4,070 ₪ ל-3,130 ₪, ונוסף החזר חשמל של 440 ₪ ברוטו. אם הנציג יעדכן את ההשתתפות ב-ATTO 3, המספרים ישתנו.  רוצה שאשווה גם לשאר החלופות הזכאיות?

</details>

### occupation_question: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'occupation'}]}} — t0 ask_representative {'question': 'העובד מציג עצמו כמפתח AI, התפקיד לא נמצא בטבלת העיסוקים, והוא ביקש לבדוק מול הנציג. הוא שואל מה יקרה לנטו אם יוותר על הרכב. רכב היום: קורולה קרוס 2025, השתתפות 300 ₪.', 'questions': [{'bound_field': 'occupation', 'occupation_query': 'מפתח AI', 'prompt_he': "האם 'מפתח AI' נחשב מפתח/ת תוכנה?"}]}
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
