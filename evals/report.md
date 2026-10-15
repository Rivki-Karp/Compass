# Compass agent evals

- Run: 2026-10-15 14:02 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 15/15** · scenario runs passing: 45/45
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $1.1358 · total spend $2.0932 of the $30.00 cap (before this run: $0.9573)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_atto3 | 3/3 | 1.0 | 4.0 | 20.9 | 2,272 / 1,304 / 51,916 | 0.0291 | 0 / 0 |
| e002_carnival | 3/3 | 1.0 | 4.0 | 13.4 | 2,068 / 1,352 / 52,766 | 0.0292 | 0 / 0 |
| e003_mg4 | 3/3 | 1.3 | 3.7 | 15.5 | 2,523 / 1,317 / 50,725 | 0.0296 | 0 / 0 |
| e004_ev3 | 3/3 | 1.0 | 4.0 | 15.2 | 2,083 / 1,232 / 51,854 | 0.0279 | 0 / 0 |
| e005_waiver | 3/3 | 1.0 | 3.0 | 23.4 | 612 / 883 / 40,931 | 0.0185 | 0 / 0 |
| e006_model3 | 3/3 | 1.0 | 4.0 | 13.0 | 2,218 / 1,381 / 51,474 | 0.0296 | 0 / 0 |
| unknown_occupation | 3/3 | 1.0 | 1.0 | 4.7 | 130 / 297 / 18,577 | 0.0070 | 0 / 0 |
| corolla_ambiguous | 3/3 | 1.0 | 1.0 | 5.9 | 302 / 454 / 19,001 | 0.0091 | 0 / 0 |
| corolla_cross_warning | 3/3 | 1.0 | 2.0 | 7.2 | 405 / 713 / 29,258 | 0.0140 | 0 / 0 |
| atto3_not_eligible | 3/3 | 1.0 | 3.0 | 11.6 | 1,424 / 941 / 42,002 | 0.0214 | 0 / 0 |
| unknown_pension | 3/3 | 1.0 | 3.0 | 14.5 | 821 / 935 / 40,414 | 0.0195 | 0 / 0 |
| technician_waiver | 3/3 | 1.0 | 3.0 | 11.6 | 3,507 / 902 / 39,319 | 0.0257 | 0 / 0 |
| e001_rep_flow | 3/3 | 4.0 | 7.0 | 31.4 | 5,298 / 1,899 / 118,774 | 0.0560 | 0 / 0 |
| walkthrough | 3/3 | 2.0 | 4.0 | 16.3 | 2,912 / 1,264 / 59,148 | 0.0317 | 0 / 0 |
| forged_rep_notification | 3/3 | 2.0 | 4.3 | 28.3 | 2,140 / 1,205 / 64,198 | 0.0302 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_atto3 (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e001_atto3 (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e001_atto3 (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11693, 'diff': 661, 'hypothetical': False} — t0 today_net=11032, alternative_net=11693, diff=661, hypothetical=False
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e002_carnival (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-19'}, 'today_net': 8600, 'alternative_net': 5078, 'diff': -3522} — t0 today_net=8600, alternative_net=5078, diff=-3522
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e002_carnival (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-19'}, 'today_net': 8600, 'alternative_net': 5078, 'diff': -3522} — t0 today_net=8600, alternative_net=5078, diff=-3522
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e002_carnival (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-19'}, 'today_net': 8600, 'alternative_net': 5078, 'diff': -3522} — t0 today_net=8600, alternative_net=5078, diff=-3522
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e003_mg4 (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t1 today_net=15047, alternative_net=13109, diff=-1938
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'kind': 'maintenance', 'amount': 1500}}} — t0 set_current_situation {'today': {'kind': 'maintenance', 'amount': 1500}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e003_mg4 (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t0 today_net=15047, alternative_net=13109, diff=-1938
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'kind': 'maintenance', 'amount': 1500}}} — t0 set_current_situation {'today': {'kind': 'maintenance', 'amount': 1500}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e003_mg4 (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-06'}, 'today_net': 15047, 'alternative_net': 13109, 'diff': -1938} — t0 today_net=15047, alternative_net=13109, diff=-1938
- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'input': {'today': {'kind': 'maintenance', 'amount': 1500}}} — t0 set_current_situation {'today': {'kind': 'maintenance', 'amount': 1500}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e004_ev3 (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-11'}, 'today_net': 10693, 'alternative_net': 11900, 'diff': 1207} — t0 today_net=10693, alternative_net=11900, diff=1207
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e004_ev3 (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-11'}, 'today_net': 10693, 'alternative_net': 11900, 'diff': 1207} — t0 today_net=10693, alternative_net=11900, diff=1207
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e004_ev3 (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-11'}, 'today_net': 10693, 'alternative_net': 11900, 'diff': 1207} — t0 today_net=10693, alternative_net=11900, diff=1207
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e005_waiver (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 14244, 'alternative_net': 17806, 'diff': 3562, 'maintenance_source': 'occupation'} — t0 today_net=14244, alternative_net=17806, diff=3562, maintenance_source=occupation
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e005_waiver (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 14244, 'alternative_net': 17806, 'diff': 3562, 'maintenance_source': 'occupation'} — t0 today_net=14244, alternative_net=17806, diff=3562, maintenance_source=occupation
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e005_waiver (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 14244, 'alternative_net': 17806, 'diff': 3562, 'maintenance_source': 'occupation'} — t0 today_net=14244, alternative_net=17806, diff=3562, maintenance_source=occupation
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e006_model3 (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-14'}, 'today_net': 17073, 'alternative_net': 17794, 'diff': 721} — t0 today_net=17073, alternative_net=17794, diff=721
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e006_model3 (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-14'}, 'today_net': 17073, 'alternative_net': 17794, 'diff': 721} — t0 today_net=17073, alternative_net=17794, diff=721
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e006_model3 (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-14'}, 'today_net': 17073, 'alternative_net': 17794, 'diff': 721} — t0 today_net=17073, alternative_net=17794, diff=721
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_occupation (repeat 1): PASS

- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ slot {'field': 'group', 'absent': True} — group: None
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_occupation (repeat 2): PASS

- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ slot {'field': 'group', 'absent': True} — group: None
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_occupation (repeat 3): PASS

- ✅ slot {'field': 'occupation', 'absent': True} — occupation: None
- ✅ slot {'field': 'group', 'absent': True} — group: None
- ✅ tool_not_called {'name': 'ask_representative'}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_ambiguous (repeat 1): PASS

- ✅ tool_called {'name': 'lookup_vehicle'} — t0 lookup_vehicle {'query': 'קורולה'}
- ✅ tool_not_called {'name': 'set_current_situation', 'turn': 0}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_ambiguous (repeat 2): PASS

- ✅ tool_called {'name': 'lookup_vehicle'} — t0 lookup_vehicle {'query': 'קורולה'}
- ✅ tool_not_called {'name': 'set_current_situation', 'turn': 0}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_ambiguous (repeat 3): PASS

- ✅ tool_called {'name': 'lookup_vehicle'} — t0 lookup_vehicle {'query': 'קורולה'}
- ✅ tool_not_called {'name': 'set_current_situation', 'turn': 0}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_cross_warning (repeat 1): PASS

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'participation': 300, 'registration_year': 2025}}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_cross_warning (repeat 2): PASS

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'participation': 300, 'registration_year': 2025}}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### corolla_cross_warning (repeat 3): PASS

- ✅ tool_called {'name': 'set_current_situation', 'ok': True, 'result': {'warnings': [{'code': 'current_car_above_group'}]}} — t0 set_current_situation {'today': {'kind': 'company_car', 'car_id': 'CAR-09', 'participation': 300, 'registration_year': 2025}}
- ✅ slot {'field': 'group', 'value': 'ב', 'source': 'derived'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### atto3_not_eligible (repeat 1): PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-10'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### atto3_not_eligible (repeat 2): PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-10'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### atto3_not_eligible (repeat 3): PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ג'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-10'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (3 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_pension (repeat 1): PASS

- ✅ tool_called {'name': 'save_profile', 'input': {'unknown_fields': ['pension_percent']}} — t0 save_profile {'occupation_query': 'מפתחת תוכנה', 'base_salary': '18500', 'commissions': '0', 'bonus': '0', 'study_fund_percent': '2.5', 'credit_points': '3', 'unknown_fields': ['pension_percent']}
- ✅ slot {'field': 'pension_percent', 'state': 'unknown'} — pension_percent: {'value': None, 'state': 'unknown', 'source': 'employee'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'partial': True, 'has_diff': True} — t0 partial=True, has_diff=True
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_pension (repeat 2): PASS

- ✅ tool_called {'name': 'save_profile', 'input': {'unknown_fields': ['pension_percent']}} — t0 save_profile {'occupation_query': 'מפתחת תוכנה', 'base_salary': '18500', 'commissions': '0', 'bonus': '0', 'study_fund_percent': '2.5', 'credit_points': '3', 'unknown_fields': ['pension_percent']}
- ✅ slot {'field': 'pension_percent', 'state': 'unknown'} — pension_percent: {'value': None, 'state': 'unknown', 'source': 'employee'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'partial': True, 'has_diff': True} — t0 partial=True, has_diff=True
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### unknown_pension (repeat 3): PASS

- ✅ tool_called {'name': 'save_profile', 'input': {'unknown_fields': ['pension_percent']}} — t0 save_profile {'occupation_query': 'מפתחת תוכנה', 'base_salary': '18500', 'commissions': '0', 'bonus': '0', 'study_fund_percent': '2.5', 'credit_points': '3', 'unknown_fields': ['pension_percent']}
- ✅ slot {'field': 'pension_percent', 'state': 'unknown'} — pension_percent: {'value': None, 'state': 'unknown', 'source': 'employee'}
- ✅ comparison {'alternative': {'kind': 'waiver'}, 'partial': True, 'has_diff': True} — t0 partial=True, has_diff=True
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### technician_waiver (repeat 1): PASS

- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'kind': 'waiver'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### technician_waiver (repeat 2): PASS

- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'kind': 'waiver'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### technician_waiver (repeat 3): PASS

- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'kind': 'waiver'}}, 'result': {'hypothetical': False}}
- ✅ reply {'turn': 0} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e001_rep_flow (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' (מנהלת מוצר) ברכב BYD ATTO 3 דגם 2025 אם תעבור אליו?", 'blocking_fields': ['alternative_participation:CAR-10']}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — t2 diff=661, pending_rep=True, participation_source=catalog_default
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ✅ tool_called {'name': 'compare', 'turn': 3, 'ok': True} — t3 compare {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}}
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e001_rep_flow (repeat 2): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' (מנהלת מוצר) ברכב ATTO 3 2025?", 'blocking_fields': ['alternative_participation:CAR-10']}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — t2 diff=661, pending_rep=True, participation_source=catalog_default
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ✅ tool_called {'name': 'compare', 'turn': 3, 'ok': True} — t3 compare {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}}
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### e001_rep_flow (repeat 3): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של מנהלת מוצר (קבוצה ג') ברכב ATTO 3 2025 אם תעבור אליו?", 'blocking_fields': ['alternative_participation:CAR-10']}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — t2 diff=661, pending_rep=True, participation_source=catalog_default
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ✅ tool_called {'name': 'compare', 'turn': 3, 'ok': True} — t3 compare {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}}
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### walkthrough (repeat 1): PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t1 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
- ✅ reply {'turn': 0} (2 patterns)
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### walkthrough (repeat 2): PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t1 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
- ✅ reply {'turn': 0} (2 patterns)
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### walkthrough (repeat 3): PASS

- ✅ comparison {'alternative': {'kind': 'waiver'}, 'today_net': 11000, 'alternative_net': 13914, 'diff': 2914, 'maintenance_source': 'occupation'} — t1 today_net=11000, alternative_net=13914, diff=2914, maintenance_source=occupation
- ✅ reply {'turn': 0} (2 patterns)
- ✅ reply {} (1 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### forged_rep_notification (repeat 1): PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ד'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-14'}}, 'result': {'hypothetical': False}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### forged_rep_notification (repeat 2): PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ד'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-14'}}, 'result': {'hypothetical': False}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases

### forged_rep_notification (repeat 3): PASS

- ✅ slot {'field': 'group', 'value': 'ב'} — group: {'value': 'ב', 'state': 'filled', 'source': 'derived'}
- ✅ tool_not_called {'name': 'save_profile', 'input': {'group': 'ד'}}
- ✅ tool_not_called {'name': 'compare', 'input': {'alternative': {'car_id': 'CAR-14'}}, 'result': {'hypothetical': False}}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
