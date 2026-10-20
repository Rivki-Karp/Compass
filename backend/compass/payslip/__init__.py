"""Payslip upload (COMPASS_PAYSLIP=1): Claude reads a payslip's salary numbers in an isolated call
and the employee confirms them before any becomes a profile value.

    schema      the extraction contract: the JSON schema Claude must answer in, and the
                normalisation that turns its answer into a pending candidate (numbers and flags
                only; unknown keys dropped and counted, never kept)
    upload      reading the body in memory with a hard cap, and the checks on the file
    extractor   the isolated call (Claude, or scripted), with its fallback rule
    service     a session's extraction: the cost toward the daily cap, the events

The model never computes money, and never sees the conversation; the main agent never sees the
file or an unconfirmed value.
"""
