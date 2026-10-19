# Compass agent evals

- Run: 2026-10-18 18:26 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 2/3** · scenario runs passing: 8/9
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.3526 · total spend $5.1248 of the $30.00 cap (before this run: $4.7722)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_rep_flow | 3/3 | 4.0 | 5.0 | 21.6 | 5,066 / 1,759 / 105,000 | 0.0512 | 0 / 0 |
| group_exception | 3/3 | 2.0 | 3.3 | 17.5 | 4,367 / 1,830 / 64,333 | 0.0421 | 0 / 0 |
| all_options | 2/3 | 1.0 | 3.0 | 11.1 | 2,274 / 938 / 45,734 | 0.0242 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_rep_flow (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' במעבר ל-BYD ATTO 3 2025 (חשמלי)?", 'blocking_fields': ['alternative_participation:CAR-10']}
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

### e001_rep_flow (repeat 2): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' במעבר לרכב ATTO 3 (2025)?", 'blocking_fields': ['alternative_participation:CAR-10']}
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

### e001_rep_flow (repeat 3): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' (מנהלת מוצר) ברכב ATTO 3 2025, אם תעבור אליו מקורולה קרוס 2025?", 'blocking_fields': ['alternative_participation:CAR-10']}
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

### group_exception (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד, מפתח תוכנה (קבוצה ב'), מחזיק קורולה קרוס 2025 (קבוצה ג') ואומר שיש לו אישור מיוחד לקבוצה ג'. נא לאשר את הקבוצה המאושרת, את גובה ההשתתפות החודשית שלו בקורולה קרוס, ואת ההשתתפות ב-ATTO 3 שהוא שוקל.", 'blocking_fields': ['current_participation', 'group_exception', 'alternative_participation:CAR-10']}
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

### group_exception (repeat 2): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד/ת בתפקיד מפתח/ת תוכנה (קבוצה ב') מחזיק/ה בקורולה קרוס 2025 (קבוצה ג') ומצהיר/ה על אישור מיוחד לקבוצה ג': האם האישור תקף, ומה ההשתתפות החודשית ברכב הנוכחי ובמעבר ל-ATTO 3 2025?", 'blocking_fields': ['current_participation', 'group_exception', 'alternative_participation:CAR-10'], 'quick_answers': [{'id': 'not_approved', 'label': "אין אישור לקבוצה ג'", 'values': {'group_exception': 'not_approved'}}]}
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

### group_exception (repeat 3): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד/ת בתפקיד מפתח תוכנה (קבוצה ב') נוהג/ת בקורולה קרוס 2025 (קבוצה ג'), מצהיר/ה על אישור מיוחד לקבוצה ג' ולא יודע/ת מהי ההשתתפות החודשית שלו/ה ברכב; נא לאשר את הקבוצה המאושרת, את ההשתתפות הנוכחית, ואת ההשתתפות ב-ATTO 3 במעבר אליו.", 'blocking_fields': ['current_participation', 'group_exception', 'alternative_participation:CAR-10'], 'quick_answers': [{'id': 'not_approved', 'label': "אין אישור לקבוצה ג'"}]}
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

### all_options (repeat 1): PASS

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ✅ reply {} (5 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### all_options (repeat 2): FAIL

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ❌ reply {} (5 patterns) — present /TUCSON/; present /MAZDA 3/
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מנהלת מוצר ← קבוצה ג', תקציב 4,500 ₪. הרכב של היום: קורולה קרוס 2025 עם השתתפות של 300 ₪, נטו משוער 11,032 ₪.  האפשרויות הזכאיות המובילות, לפי ההפרש בנטו המשוער: - **ויתור על הרכב:** נטו 14,231 ₪ (+3,199 ₪). החישוב מתייחס לשכר בלבד, ועלויות רכב פרטי אינן כלולות. - **MG4 (חשמלי, קבוצה ב'):** נטו 12,045 ₪ (+1,013 ₪). - **BYD DOLPHIN (חשמלי, קבוצה א'):** נטו 12,026 ₪ (+994 ₪).  בין האפשרויות הזכאיות יש גם רכבים בנזין, היברידיים וחשמליים נוספים, כמו KONA EV ו-EV3. ההפרש בחלקם שלילי, למשל MAZDA 3 (‎-286 ₪) ו-TUCSON (‎-440 ₪).  ההשתתפות ברכבים החדשים היא ברירת המחדל מהקטלוג, ונציג יכול לאשר אותה. רכבי קבוצה ד' אינם זמינים לך. המסלול המשפחתי (SANTA FE ו-CARNIVAL) לא זמין לך בגלל מספר הילדים.  את כל החלופות אפשר לראות ולבחור במסך. להשוות לעומק אחת מהן?

</details>

### all_options (repeat 3): PASS

- ✅ tool_called {'name': 'list_options', 'ok': True} — t0 list_options {}
- ✅ reply {} (5 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
