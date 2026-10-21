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
    source      TEXT NOT NULL CHECK (
        source IN ('employee', 'payslip', 'representative', 'derived', 'previous')
    ),
    updated_at  TEXT NOT NULL,
    -- source 'previous' only: when the value was first confirmed, in the conversation it came from
    previous_from TEXT,
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

-- User accounts (COMPASS_AUTH=1; compass/state/accounts.py). Created always, read only with the
-- flag on. No password, invite code or token is stored: only their hashes.
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,  -- trimmed, NFKC, lower-case (compass/auth/emails.py)
    name           TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    role           TEXT NOT NULL CHECK (role IN ('employee', 'rep', 'admin')),
    password_hash  TEXT NOT NULL,  -- argon2id
    status         TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
    created_at     TEXT NOT NULL,
    last_login_at  TEXT
);

CREATE TABLE IF NOT EXISTS invites (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('employee', 'rep', 'admin')),
    code_hash   TEXT NOT NULL UNIQUE,  -- SHA-256 of the code
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT
);
-- one active (unused) invite per email: a new invite replaces the old one
CREATE UNIQUE INDEX IF NOT EXISTS invites_one_active ON invites (email) WHERE used_at IS NULL;

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash    TEXT PRIMARY KEY,  -- SHA-256 of the bearer token
    user_id       TEXT NOT NULL REFERENCES users (id),
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    revoked_at    TEXT
);
CREATE INDEX IF NOT EXISTS auth_sessions_by_user ON auth_sessions (user_id);

-- The details an account chose to have remembered (COMPASS_PROFILE_MEMORY=1; compass/profile_memory.py):
-- {field: {value, source, saved_at, from_session}} for the occupation, the salary fields and
-- today's car only. Never the group, a rep's answer about a car, a payslip file or an id. Owner
-- only; deleted with the account, or by the employee. Created always, read only with the flag on.
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     TEXT PRIMARY KEY,
    fields_json TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
