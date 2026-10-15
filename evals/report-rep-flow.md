# Compass agent evals

- Run: 2026-10-15 14:21 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 1/1** · scenario runs passing: 3/3
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.1868 · total spend $2.6993 of the $30.00 cap (before this run: $2.5125)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| e001_rep_flow | 3/3 | 4.0 | 7.0 | 32.6 | 8,201 / 1,864 / 115,637 | 0.0623 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### e001_rep_flow (repeat 1): PASS

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "עובדת בקבוצה ג' שוקלת לעבור מקורולה קרוס 2025 ל-BYD ATTO 3 2025 (חשמלי). מהי ההשתתפות החודשית שלה ב-ATTO 3?", 'blocking_fields': ['alternative_participation:CAR-10']}
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': 'מה ההשתתפות החודשית של עובדת בקבוצה ג׳ שעוברת מקורולה קרוס 2025 ל-BYD ATTO 3 2025?', 'blocking_fields': ['alternative_participation:CAR-10']}
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

- ✅ tool_called {'name': 'ask_representative', 'ok': True, 'input': {'blocking_fields': ['alternative_participation:CAR-10']}} — t2 ask_representative {'question': "מהי ההשתתפות החודשית של עובדת בקבוצה ג' ברכב ATTO 3 2025 (חשמלי) אם תעבור אליו מקורולה קרוס 2025?", 'blocking_fields': ['alternative_participation:CAR-10']}
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'turn': 2, 'diff': 661, 'pending_rep': True, 'participation_source': 'catalog_default'} — t2 diff=661, pending_rep=True, participation_source=catalog_default
- ✅ comparison {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}, 'today_net': 11032, 'alternative_net': 11643, 'diff': 611, 'pending_rep': False, 'participation_source': 'representative'} — t3 today_net=11032, alternative_net=11643, diff=611, pending_rep=False, participation_source=representative
- ✅ tool_called {'name': 'compare', 'turn': 3, 'ok': True} — t3 compare {'alternative': {'kind': 'car', 'car_id': 'CAR-10'}}
- ✅ reply {'turn': 2} (1 patterns)
- ✅ slot {'field': 'alternative_participation:CAR-10', 'source': 'representative'} — alternative_participation:CAR-10: {'value': {'amount': '350', 'effective_from': None}, 'state': 'filled', 'source': 'representative'}
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
