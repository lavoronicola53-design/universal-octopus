-- init_db.sql
--
-- Schema di riferimento (documentazione): le tabelle vengono create
-- automaticamente da SQLAlchemy (`init_db()` in app/database.py) allo
-- startup dell'app. Questo file e' fornito come riferimento leggibile
-- dello schema e puo' essere eseguito manualmente in ambienti dove non
-- si vuole delegare la creazione tabelle all'ORM.

CREATE TABLE IF NOT EXISTS pattern_definitions (
    id            VARCHAR PRIMARY KEY,
    label         VARCHAR NOT NULL,
    min_candles   INTEGER NOT NULL,
    max_candles   INTEGER NOT NULL,
    description   TEXT,
    is_custom     BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prediction_records (
    id                     VARCHAR PRIMARY KEY,
    market                 VARCHAR NOT NULL,
    timeframe              VARCHAR NOT NULL,
    fractal_start_ts       DOUBLE PRECISION NOT NULL,
    fractal_end_ts         DOUBLE PRECISION NOT NULL,
    pattern_id             VARCHAR REFERENCES pattern_definitions(id),
    n_components           INTEGER NOT NULL,
    horizon                INTEGER NOT NULL,
    n_scenarios            INTEGER NOT NULL,
    dominant_scenario_id   VARCHAR NOT NULL,
    dominant_score         DOUBLE PRECISION NOT NULL,
    created_at             TIMESTAMP DEFAULT NOW(),
    outcome_recorded       BOOLEAN DEFAULT FALSE,
    outcome_error_pct      DOUBLE PRECISION,
    outcome_hit            BOOLEAN,
    outcome_checked_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenario_records (
    id                    VARCHAR PRIMARY KEY,
    prediction_id         VARCHAR NOT NULL REFERENCES prediction_records(id) ON DELETE CASCADE,
    scenario_label         VARCHAR NOT NULL,
    transform_label        VARCHAR NOT NULL,
    score                  DOUBLE PRECISION NOT NULL,
    probability            DOUBLE PRECISION NOT NULL,
    is_dominant            BOOLEAN DEFAULT FALSE,
    metrics_json           JSONB NOT NULL,
    future_candles_json    JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prediction_market ON prediction_records (market, timeframe);
CREATE INDEX IF NOT EXISTS idx_scenario_prediction ON scenario_records (prediction_id);
