-- Modelo dimensional (star schema) do data mart de seguros.
-- Dimensões conformadas são compartilhadas por todas as tabelas fato.

DROP TABLE IF EXISTS fact_funnel_event;
DROP TABLE IF EXISTS fact_claim;
DROP TABLE IF EXISTS fact_policy_month;
DROP TABLE IF EXISTS fact_policy;
DROP TABLE IF EXISTS dim_channel;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,      -- yyyymmdd
    full_date       TEXT    NOT NULL,         -- ISO 8601
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    year_month      TEXT    NOT NULL,         -- yyyy-mm
    day_of_week     INTEGER NOT NULL,         -- 0 = segunda
    is_weekend      INTEGER NOT NULL
);

CREATE TABLE dim_customer (
    customer_key      INTEGER PRIMARY KEY,
    gender            TEXT,
    state             TEXT NOT NULL,          -- 'ND' quando não informado
    region            TEXT NOT NULL,
    income_band       TEXT NOT NULL,
    segment           TEXT NOT NULL,
    age               INTEGER,                -- na data de referência
    age_band          TEXT NOT NULL,
    account_open_date_key INTEGER REFERENCES dim_date(date_key)
);

CREATE TABLE dim_product (
    product_key     INTEGER PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    base_premium    REAL NOT NULL
);

CREATE TABLE dim_channel (
    channel_key     INTEGER PRIMARY KEY,
    channel_name    TEXT NOT NULL,
    channel_type    TEXT NOT NULL             -- digital | parceiro
);

-- Grão: uma linha por apólice (fato acumulativo de ciclo de vida).
CREATE TABLE fact_policy (
    policy_id            INTEGER PRIMARY KEY,
    customer_key         INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key          INTEGER NOT NULL REFERENCES dim_product(product_key),
    channel_key          INTEGER NOT NULL REFERENCES dim_channel(channel_key),
    start_date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    cancel_date_key      INTEGER REFERENCES dim_date(date_key),
    payment_method       TEXT    NOT NULL,
    status               TEXT    NOT NULL,
    monthly_premium      REAL    NOT NULL CHECK (monthly_premium > 0),
    customer_age_at_start INTEGER,
    tenure_days          INTEGER NOT NULL     -- dias de vigência até o cancelamento ou a data de referência
);

-- Grão: uma linha por apólice por mês de vigência (snapshot periódico).
CREATE TABLE fact_policy_month (
    policy_id            INTEGER NOT NULL REFERENCES fact_policy(policy_id),
    month_key            INTEGER NOT NULL REFERENCES dim_date(date_key),  -- primeiro dia do mês
    customer_key         INTEGER NOT NULL,
    product_key          INTEGER NOT NULL,
    channel_key          INTEGER NOT NULL,
    months_since_start   INTEGER NOT NULL,
    exposure_days        INTEGER NOT NULL,
    earned_premium       REAL    NOT NULL,
    is_new               INTEGER NOT NULL,
    is_cancelled         INTEGER NOT NULL,
    is_active_eom        INTEGER NOT NULL,    -- ativa no fim do mês
    PRIMARY KEY (policy_id, month_key)
);

-- Grão: uma linha por aviso de sinistro.
CREATE TABLE fact_claim (
    claim_id             INTEGER PRIMARY KEY,
    policy_id            INTEGER NOT NULL REFERENCES fact_policy(policy_id),
    customer_key         INTEGER NOT NULL,
    product_key          INTEGER NOT NULL,
    claim_date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    claim_status         TEXT    NOT NULL,
    claim_amount         REAL    NOT NULL,
    paid_amount          REAL    NOT NULL,
    days_since_start     INTEGER NOT NULL
);

-- Grão: uma linha por evento de jornada digital.
CREATE TABLE fact_funnel_event (
    event_id             INTEGER PRIMARY KEY,
    session_id           INTEGER NOT NULL,
    customer_key         INTEGER NOT NULL,
    product_key          INTEGER NOT NULL,
    channel_key          INTEGER NOT NULL,
    date_key             INTEGER NOT NULL REFERENCES dim_date(date_key),
    step                 TEXT    NOT NULL,
    step_order           INTEGER NOT NULL,
    event_ts             TEXT    NOT NULL
);

CREATE INDEX ix_policy_month_month ON fact_policy_month(month_key);
CREATE INDEX ix_claim_policy ON fact_claim(policy_id);
CREATE INDEX ix_funnel_session ON fact_funnel_event(session_id);
