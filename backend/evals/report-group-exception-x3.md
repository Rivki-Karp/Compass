# Compass agent evals

- Run: 2026-10-19 16:05 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 1/1** · scenario runs passing: 3/3
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.1690 · total spend $7.1263 of the $30.00 cap (before this run: $6.9573)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| group_exception | 3/3 | 2.0 | 3.3 | 22.2 | 9,174 / 1,941 / 70,026 | 0.0563 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### group_exception (repeat 1): PASS

- ✅ ticket {'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'allow_pending_participation': True} — tickets: [{'bound_fields': ['current_participation', 'group_exception', 'alternative_participation:CAR-10'], 'free_types': [], 'occupation_options_from_table': False}]
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

- ✅ ticket {'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'allow_pending_participation': True} — tickets: [{'bound_fields': ['group_exception', 'current_participation', 'alternative_participation:CAR-10'], 'free_types': [], 'occupation_options_from_table': False}]
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

- ✅ ticket {'bound_fields': ['current_participation', 'group_exception'], 'free_types': [], 'allow_pending_participation': True} — tickets: [{'bound_fields': ['group_exception', 'current_participation', 'alternative_participation:CAR-10'], 'free_types': [], 'occupation_options_from_table': False}]
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
