-- PostgreSQL schema for the Freelance Intelligence Platform
-- Requires: CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Reference tables
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  full_name TEXT,
  timezone TEXT,
  locale TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  connector_version TEXT,
  config JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  match_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.50,
  preferred_sources UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
  excluded_sources UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
  preferred_roles TEXT[],
  preferred_locations TEXT[],
  preferred_skills TEXT[],
  salary_floor NUMERIC,
  salary_ceiling NUMERIC,
  notification_channels TEXT[] NOT NULL DEFAULT ARRAY['email']::TEXT[],
  advanced_preferences JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE saved_searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  criteria JSONB NOT NULL,
  schedule JSONB,
  last_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, name)
);

CREATE TYPE job_status AS ENUM ('new','open','applied','closed','archived','duplicate','expired');
CREATE TYPE proposal_status AS ENUM ('draft','submitted','accepted','rejected','withdrawn','failed');
CREATE TYPE notification_status AS ENUM ('pending','sent','failed','skipped');
CREATE TYPE notification_channel AS ENUM ('email','sms','slack','push','digest');

CREATE TABLE scraper_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running',
  total_jobs INT NOT NULL DEFAULT 0,
  new_jobs INT NOT NULL DEFAULT 0,
  updated_jobs INT NOT NULL DEFAULT 0,
  duplicate_jobs INT NOT NULL DEFAULT 0,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE scraper_errors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  scraper_run_id UUID REFERENCES scraper_runs(id) ON DELETE SET NULL,
  error_code TEXT,
  message TEXT,
  severity TEXT NOT NULL DEFAULT 'error',
  context JSONB,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- High-volume jobs table partitioned by ingestion date
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  external_id TEXT NOT NULL,
  duplicate_group_id UUID REFERENCES job_duplicate_groups(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  company TEXT,
  location TEXT,
  remote BOOLEAN NOT NULL DEFAULT FALSE,
  posted_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  status job_status NOT NULL DEFAULT 'new',
  salary_min NUMERIC,
  salary_max NUMERIC,
  currency TEXT,
  job_type TEXT,
  seniority TEXT,
  url TEXT NOT NULL,
  raw_payload JSONB,
  normalized_payload JSONB,
  search_vector tsvector,
  fingerprint TEXT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
) PARTITION BY RANGE (ingested_at);

CREATE TABLE jobs_default PARTITION OF jobs DEFAULT;

CREATE TABLE job_duplicate_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reason TEXT,
  fingerprint TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE job_duplicates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  duplicate_group_id UUID NOT NULL REFERENCES job_duplicate_groups(id) ON DELETE CASCADE,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  is_canonical BOOLEAN NOT NULL DEFAULT FALSE,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reason TEXT
);

CREATE TABLE job_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  external_id TEXT NOT NULL,
  title TEXT NOT NULL,
  company TEXT,
  location TEXT,
  remote BOOLEAN NOT NULL DEFAULT FALSE,
  posted_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  status job_status NOT NULL,
  salary_min NUMERIC,
  salary_max NUMERIC,
  currency TEXT,
  job_type TEXT,
  seniority TEXT,
  url TEXT NOT NULL,
  raw_payload JSONB,
  normalized_payload JSONB,
  fingerprint TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (recorded_at);

CREATE TABLE job_history_default PARTITION OF job_history DEFAULT;

CREATE TABLE job_ai_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  score_type TEXT NOT NULL,
  score_value NUMERIC(6,4) NOT NULL,
  details JSONB,
  model_name TEXT,
  scored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(job_id, user_id, score_type, model_name)
);

CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  saved_search_id UUID REFERENCES saved_searches(id) ON DELETE SET NULL,
  channel notification_channel NOT NULL,
  status notification_status NOT NULL DEFAULT 'pending',
  template_name TEXT,
  payload JSONB,
  attempt_count INT NOT NULL DEFAULT 0,
  last_attempt_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notification_deliveries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  channel notification_channel NOT NULL,
  status notification_status NOT NULL,
  provider_response JSONB,
  delivered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
  status proposal_status NOT NULL DEFAULT 'draft',
  cover_letter TEXT,
  attachments JSONB,
  submission_payload JSONB,
  submitted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE proposal_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  previous_status proposal_status NOT NULL,
  new_status proposal_status NOT NULL,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  comment TEXT
);

CREATE TABLE metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  metric_name TEXT NOT NULL,
  metric_type TEXT NOT NULL,
  value NUMERIC NOT NULL,
  tags JSONB,
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
  scraper_run_id UUID REFERENCES scraper_runs(id) ON DELETE SET NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (recorded_at);

CREATE TABLE metrics_default PARTITION OF metrics DEFAULT;

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted_at ON users(deleted_at);
CREATE INDEX idx_sources_domain ON sources(domain);
CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX idx_saved_searches_user_id ON saved_searches(user_id);
CREATE INDEX idx_saved_searches_active ON saved_searches(user_id, is_active);
CREATE INDEX idx_scraper_runs_source_started ON scraper_runs(source_id, started_at DESC);
CREATE INDEX idx_scraper_errors_source_occurred ON scraper_errors(source_id, occurred_at DESC);
CREATE INDEX idx_jobs_source_external ON jobs(source_id, external_id);
CREATE INDEX idx_jobs_duplicate_group ON jobs(duplicate_group_id);
CREATE INDEX idx_jobs_status_ingested ON jobs(status, ingested_at DESC);
CREATE INDEX idx_jobs_ingested_at ON jobs(ingested_at DESC);
CREATE INDEX idx_jobs_search_vector ON jobs USING GIN(search_vector);
CREATE INDEX idx_jobs_fingerprint ON jobs(fingerprint);
CREATE INDEX idx_job_history_job_recorded ON job_history(job_id, recorded_at DESC);
CREATE INDEX idx_job_ai_scores_job_user ON job_ai_scores(job_id, user_id, score_type);
CREATE INDEX idx_notifications_user_status ON notifications(user_id, status, created_at DESC);
CREATE INDEX idx_notifications_updated_at ON notifications(updated_at DESC);
CREATE INDEX idx_notification_deliveries_notification ON notification_deliveries(notification_id);
CREATE INDEX idx_proposals_user_job_status ON proposals(user_id, job_id, status);
CREATE INDEX idx_proposal_history_proposal ON proposal_history(proposal_id, changed_at DESC);
CREATE INDEX idx_metrics_name_recorded ON metrics(metric_name, recorded_at DESC);

-- Trigger templates for timestamp management
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER sources_updated_at BEFORE UPDATE ON sources FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER user_preferences_updated_at BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER saved_searches_updated_at BEFORE UPDATE ON saved_searches FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER scraper_runs_updated_at BEFORE UPDATE ON scraper_runs FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER notifications_updated_at BEFORE UPDATE ON notifications FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER proposals_updated_at BEFORE UPDATE ON proposals FOR EACH ROW EXECUTE FUNCTION update_timestamp();
