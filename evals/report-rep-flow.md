# Compass agent evals

- Run: 2026-10-16 11:07 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 0/1** · scenario runs passing: 0/1
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.0699 · total spend $2.9675 of the $30.00 cap (before this run: $2.8976)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_rep_flow | 0/1 | 4.0 | 6.0 | 26.0 | 13,335 / 1,718 / 96,904 | 0.0699 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_rep_flow: FAIL

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' במעבר ל-BYD ATTO 3 משנת 2025?", 'blocking_fields': ['alternative_participation:CAR-10']}
- ❌ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — no comparison matches
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ❌ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 3, 'origin': 'server', 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — no comparison matches
- ✅ reply {'turn': 3} (1 patterns)
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

<details><summary>Replies</summary>

- t0 [reply] רשמתי: מנהלת מוצר, שכר בסיס 18,500 ₪. מהתפקיד נגזרה קבוצה ג', תקציב 4,500 ₪. אם זה לא נכון, אפשר לתקן.  כמה שאלות להמשך: 1. יש לך עמלות חודשיות? אם כן, כמה? 2. יש לך בונוסים חודשיים? אם כן, כמה? 3. מה אחוז ההפקדה שלך לפנסיה, ומה אחוז ההפקדה שלך לקרן השתלמות? 4. כמה נקודות זיכוי יש לך?  אם חלק מהנתונים לא ידועים, אפשר לכתוב "לא יודעת" או להעלות תלוש שכר.
- t1 [reply] רשמתי את כל הנתונים: - אין עמלות ואין בונוסים. - פנסיה 6%. - קרן השתלמות 2.5%. - 2.75 נקודות זיכוי. - 2 ילדים מתחת לגיל 23. - הרכב הנוכחי: קורולה קרוס 2025, קבוצה ג', השתתפות 300 ₪.  מה תרצי לבדוק? אפשר להשוות לרכב אחר, לרכב חשמלי, למסלול משפחתי או לוויתור על הרכב. אפשר גם להציג את כל החלופות הזכאיות.
- t2 [reply] פתחתי פנייה לנציג בשאלה מהי ההשתתפות שלך ב-ATTO 3 2025. הרכב הזה זכאי לך, כי הוא בקבוצה ג' כמו הקבוצה שלך.  אפשר להמשיך בינתיים. התשובה של הנציג תופיע גם בצ'אט, גם אם תצאי.  עד שהנציג יאשר, אחשב עם ברירת המחדל מהקטלוג. רוצה שאריץ את ההשוואה עכשיו?
- t3 [reply] הנציג ענה שההשתתפות שלך ב-ATTO 3 תהיה 350 ₪.  במעבר, שווי השימוש יורד מ-4,070 ₪ ל-3,130 ₪, ולכן המס יורד. בנוסף יש תוספת בגין רכב חשמלי: 440 ₪ ברוטו, שהם 250 ₪ נטו. ההשתתפות עולה מ-300 ₪ ל-350 ₪.  הנטו המשוער שלך יהיה 11,643 ₪, לעומת 11,032 ₪ היום. ההפרש הוא ‎+611 ₪.  רוצה להשוות גם לשאר החלופות?

</details>
