# Compass agent evals

- Run: 2026-10-20 17:38 UTC · model `claude-sonnet-5-5` · effort `low` · repeat 3
- **Scenarios passing (every repeat): 1/1** · scenario runs passing: 3/3
- **Shown replies failing the guard: 0** · guard retries: 0 · template fallbacks: 0
- Cost of this run: $0.0676 · total spend $12.2751 of the $30.00 cap (before this run: $12.2074)

| Scenario | Pass | Turns | Tool rounds | Latency s | Tokens in / out / cache read | Cost $ | Guard retries / templates |
|---|---|---|---|---|---|---|---|
| payslip_flag_off | 3/3 | 1.0 | 1.0 | 6.4 | 5,300 / 404 / 26,261 | 0.0225 | 0 / 0 |

Per-scenario figures are averages over the repeats.

## Checks

### payslip_flag_off (repeat 1): PASS

- ✅ no_template {}
- ✅ reply {'turn': 0} (5 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### payslip_flag_off (repeat 2): PASS

- ✅ no_template {}
- ✅ reply {'turn': 0} (5 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one

### payslip_flag_off (repeat 3): PASS

- ✅ no_template {}
- ✅ reply {'turn': 0} (5 patterns)
- ✅ [global] script ran as written
- ✅ [global] no agent errors
- ✅ [global] shown numbers pass the guard
- ✅ [global] no forbidden phrases
- ✅ [global] no payslip unless the employee mentioned one
