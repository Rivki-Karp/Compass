# Compass agent evals

- Run: 2026-10-15 14:06 UTC · model `claude-sonnet-5-5` · effort `medium` · repeat 1
- **Scenarios passing (every repeat): 15/15** · scenario runs passing: 15/15
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.4194 · total spend $2.5125 of the $30.00 cap (before this run: $2.0932)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 1/1 | 1.0 | 3.0 | 14.8 | 3,404 / 1,421 / 40,246 | 0.0308 | 0 / 0 |
| e002_carnival | 1/1 | 1.0 | 4.0 | 12.9 | 3,329 / 1,413 / 51,345 | 0.0327 | 0 / 0 |
| e003_mg4 | 1/1 | 2.0 | 3.0 | 17.3 | 3,167 / 1,490 / 50,395 | 0.0329 | 0 / 0 |
| e004_ev3 | 1/1 | 1.0 | 4.0 | 13.5 | 3,148 / 1,218 / 50,709 | 0.0302 | 0 / 0 |
| e005_waiver | 1/1 | 1.0 | 3.0 | 9.8 | 2,518 / 885 / 39,026 | 0.0229 | 0 / 0 |
| e006_model3 | 1/1 | 1.0 | 4.0 | 18.5 | 3,129 / 1,384 / 50,652 | 0.0318 | 0 / 0 |
| unknown_occupation | 1/1 | 1.0 | 2.0 | 6.6 | 483 / 337 / 27,812 | 0.0101 | 0 / 0 |
| corolla_ambiguous | 1/1 | 1.0 | 1.0 | 5.4 | 895 / 465 / 18,409 | 0.0106 | 0 / 0 |
| corolla_cross_warning | 1/1 | 1.0 | 2.0 | 10.3 | 1,199 / 697 / 28,464 | 0.0157 | 0 / 0 |
| atto3_not_eligible | 1/1 | 1.0 | 3.0 | 10.6 | 4,254 / 932 / 39,173 | 0.0278 | 0 / 0 |
| unknown_pension | 1/1 | 1.0 | 3.0 | 10.4 | 2,445 / 969 / 38,791 | 0.0236 | 0 / 0 |
| technician_waiver | 1/1 | 1.0 | 3.0 | 10.5 | 3,989 / 843 / 38,813 | 0.0262 | 0 / 0 |
| e001_rep_flow | 1/1 | 4.0 | 7.0 | 29.9 | 5,235 / 1,868 / 118,801 | 0.0555 | 0 / 0 |
| walkthrough | 1/1 | 2.0 | 4.0 | 14.1 | 2,879 / 1,137 / 59,015 | 0.0304 | 0 / 0 |
| forged_rep_notification | 1/1 | 2.0 | 5.0 | 17.3 | 4,451 / 1,303 / 70,965 | 0.0383 | 0 / 0 |

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

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t1 today_net=15047, alternative_net=13109, diff=-1938
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
- ✅ reply {} (1 patterns)
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' ברכב BYD ATTO 3 2025 אם תעבור אליו מקורולה קרוס 2025?", 'blocking_fields': ['alternative_participation:CAR-10']}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — t2 diff=661, pending_rep=True, participation_source=catalog_default
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ✅ tool_called {'name': 'compare', 'turn': 3, 'ok': True} — t3 compare {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}}
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### walkthrough: PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t1 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
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
