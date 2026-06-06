CREATE TABLE companies (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(32) NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    primary_sector VARCHAR(64),
    isin VARCHAR(32),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE annual_report_sources (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id),
    fiscal_year VARCHAR(16) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_url TEXT,
    source_hash VARCHAR(128),
    parsed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, fiscal_year, source_hash)
);

CREATE TABLE company_segments (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id),
    fiscal_year VARCHAR(16) NOT NULL,
    segment_name VARCHAR(255) NOT NULL,
    sector_code VARCHAR(64) NOT NULL,
    revenue_share NUMERIC(8, 6) NOT NULL CHECK (revenue_share >= 0 AND revenue_share <= 1),
    policy_sensitivity NUMERIC(8, 6) NOT NULL CHECK (policy_sensitivity >= 0 AND policy_sensitivity <= 1),
    annual_report_signal NUMERIC(8, 6) NOT NULL CHECK (annual_report_signal >= 0 AND annual_report_signal <= 1),
    revenue_amount NUMERIC(20, 2),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_company_segments_company_year
    ON company_segments(company_id, fiscal_year);

CREATE TABLE exposure_refresh_runs (
    id BIGSERIAL PRIMARY KEY,
    refresh_mode VARCHAR(32) NOT NULL,
    fundamentals_as_of DATE,
    formula_version VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE exposure_scores (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id),
    refresh_run_id BIGINT NOT NULL REFERENCES exposure_refresh_runs(id),
    fiscal_year VARCHAR(16) NOT NULL,
    score_1_to_5 SMALLINT NOT NULL CHECK (score_1_to_5 BETWEEN 1 AND 5),
    raw_score NUMERIC(8, 6) NOT NULL CHECK (raw_score >= 0 AND raw_score <= 1),
    revenue_factor NUMERIC(8, 6) NOT NULL,
    business_mix_factor NUMERIC(8, 6) NOT NULL,
    annual_report_factor NUMERIC(8, 6) NOT NULL,
    sector_concentration_factor NUMERIC(8, 6) NOT NULL,
    dominant_sector VARCHAR(64),
    inputs_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_exposure_scores_company_created
    ON exposure_scores(company_id, created_at DESC);
