# Compass agent evals

- Run: 2026-10-18 17:15 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 1
- **Scenarios passing (every repeat): 16/16** · scenario runs passing: 16/16
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.4589 · total spend $4.1650 of the $30.00 cap (before this run: $3.7061)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 3.0 | 12.7 | 13,163 / 1,203 / 33,477 | 0.0516 | 0 / 0 |
| e002_carnival | 1/1 | 1.0 | 3.0 | 11.2 | 3,234 / 1,223 / 43,829 | 0.0291 | 0 / 0 |
| e003_mg4 | 1/1 | 1.0 | 3.0 | 11.1 | 2,632 / 1,161 / 42,840 | 0.0268 | 0 / 0 |
| e004_ev3 | 1/1 | 1.0 | 3.0 | 11.8 | 3,180 / 1,323 / 43,383 | 0.0299 | 0 / 0 |
| e005_waiver | 1/1 | 1.0 | 3.0 | 9.4 | 2,504 / 893 / 42,802 | 0.0237 | 0 / 0 |
| e006_model3 | 1/1 | 1.0 | 3.0 | 11.6 | 2,959 / 1,269 / 43,276 | 0.0287 | 0 / 0 |
| unknown_occupation | 1/1 | 1.0 | 1.0 | 5.1 | 366 / 266 / 20,230 | 0.0076 | 0 / 0 |
| corolla_ambiguous | 1/1 | 1.0 | 1.0 | 4.3 | 881 / 438 / 20,311 | 0.0106 | 0 / 0 |
| corolla_cross_warning | 1/1 | 1.0 | 2.0 | 7.6 | 1,185 / 673 / 31,303 | 0.0159 | 0 / 0 |
| atto3_not_eligible | 1/1 | 1.0 | 3.0 | 10.3 | 4,145 / 981 / 42,949 | 0.0288 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 3.0 | 10.0 | 2,425 / 980 / 42,555 | 0.0244 | 0 / 0 |
| technician_waiver | 1/1 | 1.0 | 3.0 | 9.7 | 3,903 / 882 / 42,589 | 0.0271 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 6.0 | 22.1 | 5,380 / 1,854 / 114,964 | 0.0550 | 0 / 0 |
| walkthrough | 1/1 | 3.0 | 4.0 | 17.9 | 3,841 / 1,681 / 76,152 | 0.0416 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 2.0 | 10.2 | 1,414 / 855 / 42,266 | 0.0205 | 0 / 0 |
| group_exception | 1/1 | 2.0 | 3.0 | 16.0 | 4,013 / 1,632 / 56,013 | 0.0375 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_atto3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e002_carnival: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-19'}, 'today_net': 8600, 'alternative_net': 5078, 'diff': -3522} — t0 today_net=8600, alternative_net=5078, diff=-3522
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e003_mg4: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t0 today_net=15047, alternative_net=13109, diff=-1938
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'kind': 'maintenance', 'amount': 1500}}} — t0 set_current_situation {'today': {'kind': 'maintenance', 'amount': 1500}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e004_ev3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-11'}, 'today_net': 10693, 'alternative_net': 11900, 'diff': 1207} — t0 today_net=10693, alternative_net=11900, diff=1207
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e005_waiver: PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 14244, 'alternative_net': 17806, 'diff': 3562, 'maintenance_source': 'occupation'} — t0 today_net=14244, alternative_net=17806, diff=3562, maintenance_source=occupation
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e006_model3: PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-14'}, 'today_net': 17073, 'alternative_net': 17794, 'diff': 721} — t0 today_net=17073, alternative_net=17794, diff=721
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_occupation: PASS

- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ slot {'field': 'group', 'absent': True} — group: None
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_ambiguous: PASS

- ✅ tool_called {'name': 'lookup_vehicle'} — t0 lookup_vehicle {'query': 'קורולה'}
- ✅ tool_not_called {'name': 'set_current_situation', 'turn': 0}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_cross_warning: PASS

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'participation': 300, 'registration_year': 2025}}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### atto3_not_eligible: PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-10'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_pension: PASS

- ✅ tool_called {'name': 'save_profile', 'input': {'unknown_fields': ['pension_percent']}} — t0 save_profile {'occupation_query': 'מפתחת תוכנה', 'base_salary': '18500', 'commissions': '0', 'bonus': '0', 'study_fund_percent': '2.5', 'credit_points': '3', 'unknown_fields': ['pension_percent']}
- ✅ slot {'field': 'pension_percent', 'state': 'unknown'} — pension_percent: {'value': None, 'state': 'unknown', 'source': 'employee'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'partial': True, 'has_diff': True} — t0 partial=True, has_diff=True
- ✅ reply {} (2 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### technician_waiver: PASS

- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'kind': 'waiver'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e001_rep_flow: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' (מנהלת מוצר) ברכב ATTO 3 2025 (CAR-10)?", 'blocking_fields': ['alternative_participation:CAR-10']}
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

### walkthrough: PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t2 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
- ✅ reply {'turn': 0} (2 patterns)
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### forged_rep_notification: PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ד'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-14'}}, 'result': {'hypothetical': False}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### group_exception: PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'turn': 0, 'input': {'blocking_fields': ['current_participation', 'group_exception']}} — t0 ask_representative {'question': "עובד/ת בתפקיד מפתח תוכנה (קבוצה ב') עם קורולה קרוס 2025 (קבוצה ג') מצהיר/ה על אישור מיוחד לקבוצה ג' ואינו/ה יודע/ת את ההשתתפות החודשית ברכב. מהי הקבוצה המאושרת, ומהי ההשתתפות הנוכחית?", 'blocking_fields': ['current_participation', 'group_exception'], 'quick_answers': [{'id': 'not_approved', 'label': "לא מאושר לקבוצה ג'"}, {'id': 'approved_c', 'label': "מאושר לקבוצה ג'", 'values': {'group_exception': 'ג'}}]}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ slot {'field': 'group', 'value': 'ג', 'source': 'representative'} — group: {'value': 'ג', 'state': 'filled', 'source': 'representative'}
- ✅ slot {'field': 'current_participation', 'source': 'representative'} — current_participation: {'value': {'amount': '300', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 1, 'today_net': 11000, 'alternative_net': 11661, 'diff': 661, 'hypothetical': False} — t1 today_net=11000, alternative_net=11661, diff=661, hypothetical=False
- ✅ reply {'turn': 1} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
