# Compass agent evals

- Run: 2026-10-18 17:16 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 1/1** · scenario runs passing: 3/3
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.1231 · total spend $4.2881 of the $30.00 cap (before this run: $4.1650)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| group_exception | 3/3 | 2.0 | 4.3 | 19.9 | 3,627 / 1,704 / 74,567 | 0.0410 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### group_exception (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד/ת בתפקיד מפתח/ת תוכנה (קבוצה ב') מחזיק/ה קורולה קרוס 2025 (קבוצה ג') ומצהיר/ה על אישור מיוחד לקבוצה ג', ואינו/ה יודע/ת את גובה ההשתתפות החודשית ברכב. נא לאשר את הקבוצה המאושרת ואת ההשתתפות הנוכחית.", 'blocking_fields': ['current_participation', 'group_exception'], 'quick_answers': [{'id': 'approved_c', 'label': "אושרה קבוצה ג', השתתפות 300 ₪", 'values': {'group_exception': 'ג', 'current_participation': 300}}, {'id': 'not_approved', 'label': 'לא מאושר, השתתפות 300 ₪', 'values': {'group_exception': 'not_approved', 'current_participation': 300}}]}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ slot {'field': 'group', 'value': 'ג', 'source': 'representative'} — group: {'value': 'ג', 'state': 'filled', 'source': 'representative'}
- ✅ slot {'field': 'current_participation', 'source': 'representative'} — current_participation: {'value': {'amount': '300', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 1, 'today_net': 11000, 'alternative_net': 11661, 'diff': 661, 'hypothetical': False} — t1 today_net=11000, alternative_net=11661, diff=661, hypothetical=False
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### group_exception (repeat 2): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד/ת בתפקיד מפתח/ת תוכנה (קבוצה ב') נוהג/ת בקורולה קרוס 2025 (קבוצה ג'), מצהיר/ה על אישור מיוחד לקבוצה ג' ולא יודע/ת מה גובה ההשתתפות החודשית ברכב. נא לאשר את הקבוצה המאושרת ואת ההשתתפות הנוכחית.", 'blocking_fields': ['current_participation', 'group_exception']}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ slot {'field': 'group', 'value': 'ג', 'source': 'representative'} — group: {'value': 'ג', 'state': 'filled', 'source': 'representative'}
- ✅ slot {'field': 'current_participation', 'source': 'representative'} — current_participation: {'value': {'amount': '300', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 1, 'today_net': 11000, 'alternative_net': 11661, 'diff': 661, 'hypothetical': False} — t1 today_net=11000, alternative_net=11661, diff=661, hypothetical=False
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### group_exception (repeat 3): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד/ת בתפקיד מפתח תוכנה (קבוצה ב') עם קורולה קרוס 2025 (קבוצה ג'): האם יש אישור חריג לקבוצה ג', ומהי ההשתתפות החודשית ברכב הנוכחי?", 'blocking_fields': ['current_participation', 'group_exception'], 'quick_answers': [{'id': 'not_approved', 'label': 'לא מאושר, השתתפות לפי ברירת מחדל', 'values': {'group_exception': 'not_approved'}}, {'id': 'approved_c', 'label': "מאושר לקבוצה ג'", 'values': {'group_exception': 'ג'}}]}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ slot {'field': 'group', 'value': 'ג', 'source': 'representative'} — group: {'value': 'ג', 'state': 'filled', 'source': 'representative'}
- ✅ slot {'field': 'current_participation', 'source': 'representative'} — current_participation: {'value': {'amount': '300', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 1, 'today_net': 11000, 'alternative_net': 11661, 'diff': 661, 'hypothetical': False} — t1 today_net=11000, alternative_net=11661, diff=661, hypothetical=False
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
