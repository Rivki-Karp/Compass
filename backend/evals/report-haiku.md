# Compass agent evals

- Run: 2026-10-20 10:02 UTC · model `claude-haiku-5-5` · effort `medium` · repeat 1
- **Scenarios passing (every repeat): 16/22** · scenario runs passing: 16/22
- **Shown replies failing the guard: 0** · guard retries: 1 · template fallbacks: 0
- Cost of this run: $0.0509 · total spend $8.6359 of the $30.00 cap (before this run: $8.5530)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 3.0 | 11.4 | 17,484 / 1,691 / 46,901 | 0.0035 | 0 / 0 |
| e002_carnival | 1/1 | 1.0 | 2.0 | 14.0 | 3,403 / 1,944 / 44,949 | 0.0018 | 0 / 0 |
| e003_mg4 | 1/1 | 2.0 | 2.0 | 13.8 | 3,067 / 1,805 / 60,430 | 0.0019 | 0 / 0 |
| e004_ev3 | 1/1 | 1.0 | 3.0 | 11.5 | 2,836 / 1,449 / 60,440 | 0.0017 | 0 / 0 |
| e005_waiver | 1/1 | 1.0 | 2.0 | 10.2 | 2,744 / 1,444 / 44,221 | 0.0015 | 0 / 0 |
| e006_model3 | 1/1 | 1.0 | 3.0 | 14.8 | 3,257 / 2,010 / 61,087 | 0.0020 | 0 / 0 |
| unknown_occupation | 0/1 | 1.0 | 1.0 | 5.4 | 468 / 610 / 28,646 | 0.0006 | 0 / 0 |
| corolla_ambiguous | 1/1 | 1.0 | 1.0 | 6.1 | 1,093 / 777 / 28,727 | 0.0008 | 0 / 0 |
| corolla_cross_warning | 0/1 | 1.0 | 3.0 | 11.6 | 2,080 / 1,693 / 59,858 | 0.0017 | 0 / 0 |
| atto3_not_eligible | 0/1 | 1.0 | 3.0 | 20.8 | 6,035 / 2,631 / 60,429 | 0.0027 | 0 / 0 |
| unknown_pension | 0/1 | 1.0 | 2.0 | 8.2 | 2,465 / 1,223 / 44,072 | 0.0014 | 0 / 0 |
| technician_waiver | 1/1 | 1.0 | 3.0 | 11.8 | 5,287 / 1,616 / 60,607 | 0.0021 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 4.0 | 24.2 | 9,467 / 3,595 / 151,355 | 0.0045 | 1 / 0 |
| walkthrough | 1/1 | 2.0 | 4.0 | 15.0 | 2,903 / 2,070 / 90,974 | 0.0023 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 4.0 | 19.6 | 7,035 / 2,940 / 98,531 | 0.0033 | 0 / 0 |
| group_exception | 1/1 | 2.0 | 5.0 | 25.4 | 5,821 / 3,739 / 113,451 | 0.0037 | 0 / 0 |
| all_options | 1/1 | 1.0 | 2.0 | 13.1 | 4,200 / 2,090 / 44,157 | 0.0020 | 0 / 0 |
| occupation_question | 1/1 | 2.0 | 3.0 | 20.4 | 4,988 / 3,099 / 79,799 | 0.0030 | 0 / 0 |
| free_question | 1/1 | 2.0 | 2.0 | 13.8 | 2,986 / 1,889 / 61,153 | 0.0019 | 0 / 0 |
| unknown_current_car | 0/1 | 2.0 | 4.0 | 19.1 | 4,781 / 2,595 / 96,383 | 0.0029 | 0 / 0 |
| rep_identifies_car | 1/1 | 2.0 | 5.0 | 25.1 | 6,853 / 3,603 / 118,134 | 0.0038 | 0 / 0 |
| options_without_current_car | 0/1 | 1.0 | 2.0 | 10.2 | 3,679 / 1,535 / 43,783 | 0.0017 | 0 / 0 |

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

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t1 today_net=15047, alternative_net=13109, diff=-1938
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

### unknown_occupation: FAIL

- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ slot {'field': 'group', 'absent': True} — group: None
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ❌ [global] no payslip unless the employee mentioned one — t0 payslip

<details><summary>Replies</summary>

- t0 [reply] רשמתי: שכר בסיס 9,000 ₪.  לא הצלחתי לזהות את התפקיד "גננת" בטבלת העיסוקים. נסי לכתוב לי את שם התפקיד הרשמי כפי שמופיע בחוזה או בתלוש, או ניסוח אחר שלו, למשל "גננת בגן ילדים" או "מורה בגן חובה". כך אוכל לקבוע את קבוצת הזכאות שלך.  בנוסף, יש לך עמלות או בונוסים חודשיים?

</details>

### corolla_ambiguous: PASS

- ✅ tool_called {'name': 'lookup_vehicle'} — t0 lookup_vehicle {'query': 'קורולה'}
- ✅ tool_not_called {'name': 'set_current_situation', 'turn': 0}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### corolla_cross_warning: FAIL

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'participation': 300, 'registration_year': 2025}}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ❌ reply {'turn': 0} (3 patterns) — missing /\?/
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מפתחת תוכנה ← קבוצה ב', תקציב 3,700 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי.  הרכב של היום נרשם: טויוטה קורולה קרוס 2025 (היברידי), קבוצה ג', והשתתפות של 300 ₪ בחודש.  הקבוצה של הרכב גבוהה מקבוצת העיסוק שלך (ב'). לכן פתחתי פנייה לנציג כדי לברר את זה. השאלה: האם יש לך אישור חריג לקבוצה ג', או שהרכב לא מאושר. עד שהנציג יענה, אפשר להמשיך. התשובה תופיע בצ'אט גם אם תצא מהשיחה.  אם יש לך אישור חריג כבר היום, כתבי לי ואעדכן. אחרת, אפשר לבחור רכב אחר שתרצי לבדוק, ואחשב את הנטו המשוער שלו לעומת היום.

</details>

### atto3_not_eligible: FAIL

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-10'}}, 'result': {'hypothetical': False}}
- ❌ reply {'turn': 0} (3 patterns) — missing /KONA\|קונה\|DOLPHIN\|דולפין/
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מפתחת תוכנה ← קבוצה ב', תקציב 3,700 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. הרכב של היום: קיה נירו 2025 עם השתתפות של 250 ₪.  הנטו המשוער היום הוא **11,539 ₪**.  **ATTO 3 לא זכאי לך**, כי הוא בקבוצה ג' והתקציב שלך הוא של קבוצה ב'. עם זאת, אפשר לחשב אותו היפותטית, בתנאי לאישור: - נטו משוער: **11,661 ₪**, הפרש **+122 ₪** לעומת היום. - שווי השימוש עולה מ-2,950 ל-3,130 ₪, וזה מוריד מהנטו. - רכב חשמלי מקבל החזר חשמל, שמוסיף כ-250 ₪ נטו. - ברירת המחדל מהקטלוג להשתתפות ב-ATTO 3 היא 300 ₪ (לעומת 250 ₪ היום), וזה מוריד 50 ₪.  הכלי מצא רק מועמד אחד ל"ATTO 3" בשנת 2025. האם מדובר ב-BYD ATTO 3 2025?  **חלופות חשמליות זכאיות בקבוצה שלך**, לפי הפרש: - MG4: נטו 12,013 ₪, הפרש **+474 ₪** - BYD Dolphin (קבוצה א'): נטו 11,994 ₪, הפרש **+455 ₪** - Kona EV: נטו 11,784 ₪, הפרש **+245 ₪**  שאר החלופות מופיעות במסך, ואפשר לבחור ביניהן שם.  האם לבדוק את ATTO 3 כחלופה היפותטית, או לחשב את אחת מהחלופות הזכאיות?

</details>

### unknown_pension: FAIL

- ✅ tool_called {'name': 'save_profile', 'input': {'unknown_fields': ['pension_percent']}} — t0 save_profile {'occupation_query': 'מפתחת תוכנה', 'base_salary': '18500', 'commissions': '0', 'bonus': '0', 'study_fund_percent': '2.5', 'credit_points': '3', 'unknown_fields': ['pension_percent']}
- ✅ slot {'field': 'pension_percent', 'state': 'unknown'} — pension_percent: {'value': None, 'state': 'unknown', 'source': 'employee'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'partial': True, 'has_diff': True} — t0 partial=True, has_diff=True
- ❌ reply {} (2 patterns) — present /תלוש/
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ❌ [global] no payslip unless the employee mentioned one — t0 payslip

<details><summary>Replies</summary>

- t0 [reply] הפרש החישוב המשוער של ויתור על ה-MG4 הוא **+1,951 ₪** לחודש לעומת היום. הנטו המלא עדיין לא מוצג, כי אחוז הפנסיה חסר.  המנגנון: שווי השימוש של הרכב (2,430 ₪) יורד מהשכר החייב במס, וגם תוספת החשמל לא נכללת יותר, כך שההכנסה החייבת יורדת. מנגד, מתווספת אחזקה של 1,500 ₪ לחודש לפי העיסוק, ואת ההשתתפות של 300 ₪ לחודש כבר לא משלמים.  החישוב מתייחס לשכר בלבד, ועלויות רכב פרטי אינן כלולות.  אם תכתבי לי את אחוז הפנסיה שלך, או שתבדקי אותו בתלוש, אחשב את הנטו המלא לשני המצבים. אפשר גם להשוות חלופות של רכבים אחרים במקום הוויתור.

</details>

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

- ✅ ticket {'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'allow_pending_participation': True} — tickets: [{'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'occupation_options_from_table': False}]
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

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {'participation': {}}
- ✅ options_reply {'top': 3} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### occupation_question: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'occupation'}]}} — t0 ask_representative {'question': 'עובד שמציין את תפקידו כ"מפתח AI". התפקיד לא נמצא בטבלת העיסוקים לפי הניסוח הזה, והעובד ביקש לבדוק מול הנציג. שכר בסיס 18,500 ₪, ללא עמלות או בונוסים, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי. הרכב של היום: קורולה קרוס 2025 (CAR-09, קבוצה ג), השתתפות 300 ₪ לחודש. העובד שואל על ויתור על הרכב, ולכן נדרשת הקבוצה הנגזרת מהעיסוק.', 'questions': [{'bound_field': 'occupation', 'occupation_query': 'מפתח AI', 'prompt_he': "לאיזה עיסוק בטבלה מתאים 'מפתח AI'? (לדוגמה: מפתח/ת תוכנה)"}]}
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0} — t0 ask_representative {'question': 'עובדת שואלת האם החברה מאפשרת לטעון רכב חשמלי בחניון של המשרדים. אין נתונים נוספים הנדרשים לחישוב.', 'questions': [{'prompt_he': 'האם החברה מאפשרת טעינה של רכב חשמלי בחניון המשרדים?', 'type': 'yes_no'}]}
- ✅ ticket {'bound_fields': [], 'free_types': ['yes_no']} — tickets: [{'bound_fields': [], 'free_types': ['yes_no'], 'occupation_options_from_table': False}]
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ slot {'field': 'occupation', 'source': 'employee'} — occupation: {'value': 'מפתח/ת תוכנה', 'state': 'filled', 'source': 'employee'}
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### unknown_current_car: FAIL

- ✅ tool_called {'name': 'search_catalog', 'ok': True, 'turn': 0} — t0 search_catalog {'query': 'יונדאי'}
- ❌ reply {'turn': 0} (3 patterns) — missing /הרכב שלי לא ברשימה/; missing /אין לי רכב היום/
- ✅ tool_not_called {'name': 'set_current_situation', 'ok': True, 'turn': 0}
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'car_id': 'CAR-08'}}} — t1 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-08', 'participation': 300, 'registration_year': 2026}}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'has_diff': True, 'today_unknown': False} — t1 has_diff=True, today_unknown=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מפתחת תוכנה ← קבוצה ב', תקציב 3,700 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6.5%, קרן השתלמות 2.5%, 3 נקודות זיכוי.  ב-MG4 (2025, חשמלי) הנטו המשוער הוא **12,013 ₪**, עם השתתפות של 250 ₪ בחודש. זו ברירת המחדל מהקטלוג, לא מה שציינת. אם תרצי להשתתף בסכום אחר ב-MG4, אפשר לעדכן.  כדי לחשב את ההפרש לעומת היום אני צריך לדעת איזה יונדאי יש לך. אלה הדגמים שמצאתי:  1. KONA EV (2026), חשמלי, קבוצה ב' 2. TUCSON (2025), בנזין, קבוצה ג' 3. SANTA FE (2025), בנזין, מסלול משפחתי  אם הרכב שלך לא ברשימה, כתבי לי את שם הדגם ואת שנת הרישום.
- t1 [reply] רשמתי: הרכב של היום הוא KONA EV (2026) עם השתתפות של 300 ₪ בחודש.  הנטו המשוער היום הוא **11,734 ₪**, וב-MG4 הוא **12,013 ₪**, כלומר ההפרש **+279 ₪** בחודש.  שני דברים משפיעים על ההפרש. שווי השימוש של MG4 נמוך יותר: 2,430 ₪ לעומת 2,960 ₪ ב-KONA EV, ולכן המס והביטוחים יורדים. מנגד, ההשתתפות ב-MG4 היא ברירת המחדל מהקטלוג, 250 ₪ במקום 300 ₪, וזה מוסיף 50 ₪ לנטו. אם תרצי להשתתף בסכום אחר ב-MG4, אפשר לעדכן ולחשב מחדש.  אני מניח שהקונה שלך הוא מדגם 2026, כפי שמופיע בקטלוג. אשמח שתאשרי את שנת הרישום.

</details>

### rep_identifies_car: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'questions': [{'bound_field': 'current_car'}]}} — t0 ask_representative {'question': 'עובדת שטראוס, מפתחת תוכנה (קבוצה ב\', תקציב 3,700 ₪). יש לה רכב חברה צמוד שאינה יודעת את דגמו; היא מתארת אותו כ"מציון". היא משתתפת בעלות ב-300 ₪ לחודש. היא מבקשת לבדוק מול הנציג איזה רכב יש לה כיום, ורוצה לדעת מה יקרה לנטו אם תעבור ל-MG4.', 'questions': [{'bound_field': 'current_car', 'car_query': 'מציון'}]}
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

### options_without_current_car: FAIL

- ✅ tool_called {'name': 'list_options', 'ok': True, 'turn': 0} — t0 list_options {}
- ✅ options_reply {'top': 3, 'turn': 0} — leads with ['ויתור', 'MG4', 'BYD DOLPHIN']; top 3 eligible ['ויתור', 'MG4', 'BYD DOLPHIN']
- ❌ reply {'turn': 0} (3 patterns) — missing /הרכב (של \|ה)?היום/
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מנהלת מוצר ← קבוצה ג', תקציב 4,500 ₪. שכר בסיס 18,500 ₪, בלי עמלות ובונוסים, פנסיה 6%, קרן השתלמות 2.5%, 2.75 נקודות זיכוי ושני ילדים מתחת לגיל 23.  מכיוון שהרכב הצמוד של היום עוד לא ידוע, אני מציג את הנטו המשוער של כל חלופה. ההפרש לעומת היום יופיע אחרי שנדע איזה רכב יש לך.  הנטו המשוער של האפשרויות המובילות: - **ויתור על רכב** (עם דמי אחזקה לפי העיסוק): 14,231 ₪ - **MG4** (חשמלי, קבוצה ב'): 12,045 ₪ - **BYD DOLPHIN** (חשמלי, קבוצה א'): 12,026 ₪  יש עוד חלופות זכאיות במסך, בהן היברידיות, בנזין וחשמליות נוספות. אפשר לראות ולבחור אותן שם. מסלול המשפחתי לא זמין כרגע לפי הכללים. חישוב הוויתור כולל רק את השכר, ועלויות של רכב פרטי אינן כלולות.  איזה רכב צמוד יש לך היום, ומה ההשתתפות החודשית שלך בו? אחרי שנדע זאת אחשב את ההפרשים.

</details>
