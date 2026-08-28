-- Runs once, automatically, the first time the `db` service initializes its data
-- directory (see docker-compose.yml volume mount to /docker-entrypoint-initdb.d).
-- Enables pgvector so later phases can store catalog embeddings.
CREATE EXTENSION IF NOT EXISTS vector;
