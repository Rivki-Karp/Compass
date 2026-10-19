-- Compass session store (data/app.db). Applied on startup if missing; see compass/state/store.py.
-- JSON columns hold plain JSON (money as strings, never floats).

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('active', 'waiting_for_rep', 'closed'))
);

CREATE TABLE IF NOT EXISTS messages (
    session_id    TEXT NOT NULL REFERENCES sessions (id),
    seq           INTEGER NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system_event')),
    content_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);

CREATE TABLE IF NOT EXISTS profile_slots (
    session_id  TEXT NOT NULL REFERENCES sessions (id),
    field       TEXT NOT NULL,
    value_json  TEXT NOT NULL,  -- JSON null unless state = 'filled'
    state       TEXT NOT NULL CHECK (state IN ('filled', 'unknown', 'pending_rep')),
    source      TEXT NOT NULL CHECK (source IN ('employee', 'payslip', 'representative', 'derived')),
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (session_id, field)
);

CREATE TABLE IF NOT EXISTS scenarios (
    session_id    TEXT NOT NULL REFERENCES sessions (id),
    kind          TEXT NOT NULL,  -- 'today' | 'alternative:<n>'
    payload_json  TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (session_id, kind)
);

CREATE TABLE IF NOT EXISTS tickets (
    id                    TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL REFERENCES sessions (id),
    question              TEXT NOT NULL,
    context_json          TEXT NOT NULL,
    blocking_fields_json  TEXT NOT NULL,
    quick_answers_json    TEXT NOT NULL,
    -- the ticket's questions (compass/tools/questions.py); NULL: a ticket stored before them,
    -- whose questions are its blocking fields. Added in place to older files (store.py).
    questions_json        TEXT,
    status                TEXT NOT NULL CHECK (status IN ('open', 'answered')),
    answer_json           TEXT,
    created_at            TEXT NOT NULL,
    answered_at           TEXT
);
CREATE INDEX IF NOT EXISTS tickets_by_status ON tickets (status, created_at);

-- Append-only: the single source for the live UI and for SSE replay (Last-Event-ID = seq).
CREATE TABLE IF NOT EXISTS events (
    session_id    TEXT NOT NULL REFERENCES sessions (id),
    seq           INTEGER NOT NULL,
    type          TEXT NOT NULL,
    payload_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);

-- Model spend per UTC day, across every session (the live server's daily cap). Micro-USD.
CREATE TABLE IF NOT EXISTS daily_spend (
    day        TEXT PRIMARY KEY,  -- YYYY-MM-DD, UTC
    micro_usd  INTEGER NOT NULL
);
