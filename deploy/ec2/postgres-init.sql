-- Extensions required by the current InsightGuide SQLAlchemy models.
-- The official PostgreSQL image creates POSTGRES_DB and its owner before this
-- file runs, so no hard-coded database or role names are needed here.
CREATE EXTENSION IF NOT EXISTS vector;
