# Duplicate Detection Engine

This FastAPI service now includes a duplicate detection engine for freelance jobs that:

- scores candidate jobs with URL, title, description, budget, company, time, and embedding-style similarity signals
- produces a duplicate confidence value
- merges duplicates while preserving source history
- exposes a small HTTP endpoint for detection and merge actions
- has a PostgreSQL-ready persistence layer for canonical jobs and source history

## Next steps

- wire the service to PostgreSQL migrations and a real embeddings provider
- replace the heuristic embedding proxy with pgvector or a hosted embedding API
- add a background ingestion worker for millions of jobs
- add indexing and candidate selection to avoid full-table scans
